import { JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import { NotebookActions, NotebookPanel, INotebookTracker } from '@jupyterlab/notebook';

const plugin: JupyterFrontEndPlugin<void> = {
  id: '@math-of-signals/autorun:plugin',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, tracker: INotebookTracker) => {
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
        await panel.sessionContext.ready;

        if (!panel.sessionContext.session?.kernel) {
          await panel.sessionContext.initialize();
          await panel.sessionContext.ready;
        }

        if (!panel.sessionContext.session?.kernel) {
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
            await NotebookActions.run(notebook, panel.sessionContext, app.commands);
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
