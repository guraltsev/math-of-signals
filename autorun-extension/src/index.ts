import { JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import {
  ISessionContextDialogs as ISessionContextDialogsToken,
  SessionContextDialogs
} from '@jupyterlab/apputils';
import type { ISessionContextDialogs } from '@jupyterlab/apputils';
import { NotebookActions, NotebookPanel, INotebookTracker } from '@jupyterlab/notebook';

const plugin: JupyterFrontEndPlugin<void> = {
  id: '@math-of-signals/autorun:plugin',
  autoStart: true,
  requires: [INotebookTracker],
  optional: [ISessionContextDialogsToken],
  activate: (
    _app: JupyterFrontEnd,
    tracker: INotebookTracker,
    sessionDialogsToken: ISessionContextDialogs | null
  ) => {
    const sessionDialogs = sessionDialogsToken ?? new SessionContextDialogs();
    const running = new WeakMap<NotebookPanel, Promise<void>>();
    const completed = new WeakSet<NotebookPanel>();

    const getAutorunIndices = (panel: NotebookPanel): number[] => {
      const model = panel.content.model;
      if (!model) {
        return [];
      }

      const indices: number[] = [];
      for (let index = 0; index < model.cells.length; index += 1) {
        if (model.cells.get(index).getMetadata('autorun') === true) {
          indices.push(index);
        }
      }
      return indices;
    };

    const ensureKernelReady = async (panel: NotebookPanel): Promise<boolean> => {
      const { sessionContext } = panel;

      if (!sessionContext.isReady) {
        const needsSelection = await sessionContext.initialize();
        if (needsSelection) {
          await sessionDialogs.selectKernel(sessionContext);
        }
      }

      await sessionContext.ready;
      return !!sessionContext.session?.kernel;
    };

    const runAutorunCells = async (panel: NotebookPanel): Promise<void> => {
      if (completed.has(panel)) {
        return;
      }
      if (running.has(panel)) {
        await running.get(panel);
        return;
      }

      const task = (async () => {
        await panel.context.ready;
        await panel.revealed;

        const hasKernel = await ensureKernelReady(panel);
        if (!hasKernel) {
          return;
        }

        const indices = getAutorunIndices(panel);
        completed.add(panel);

        if (!indices.length) {
          return;
        }

        const notebook = panel.content;
        const previousActiveCellIndex = notebook.activeCellIndex;

        try {
          for (const index of indices) {
            notebook.activeCellIndex = index;
            await NotebookActions.run(notebook, panel.sessionContext, sessionDialogs);
          }
        } finally {
          notebook.activeCellIndex = previousActiveCellIndex;
        }
      })();

      running.set(panel, task);
      try {
        await task;
      } finally {
        running.delete(panel);
      }
    };

    const registerPanel = (panel: NotebookPanel): void => {
      void runAutorunCells(panel);
    };

    tracker.widgetAdded.connect((_, panel) => {
      registerPanel(panel);
    });

    tracker.forEach(panel => {
      registerPanel(panel);
    });
  }
};

export default plugin;
