import { JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import {
  ISessionContextDialogs as ISessionContextDialogsToken,
  SessionContextDialogs
} from '@jupyterlab/apputils';
import type { ISessionContextDialogs } from '@jupyterlab/apputils';
import { NotebookActions, NotebookPanel, INotebookTracker } from '@jupyterlab/notebook';

const PLUGIN_ID = '@math-of-signals/autorun:plugin';
const AUTORUN_TAG = 'autorun';
const AUTORUN_METADATA_KEY = 'autorun';

const plugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [INotebookTracker],
  optional: [ISessionContextDialogsToken],
  activate: (
    _app: JupyterFrontEnd,
    tracker: INotebookTracker,
    sessionDialogsToken: ISessionContextDialogs | null
  ) => {
    console.info(`[${PLUGIN_ID}] plugin loaded`);

    const sessionDialogs = sessionDialogsToken ?? new SessionContextDialogs();
    const running = new WeakMap<NotebookPanel, Promise<void>>();
    const completed = new WeakSet<NotebookPanel>();

    const getNotebookLabel = (panel: NotebookPanel): string => {
      return panel.context.path || panel.title.label || '<unknown notebook>';
    };

    const hasAutorunTag = (value: unknown): boolean => {
      return Array.isArray(value) && value.includes(AUTORUN_TAG);
    };

    const getAutorunIndices = (panel: NotebookPanel): number[] => {
      const model = panel.content.model;
      if (!model) {
        console.info(`[${PLUGIN_ID}] no notebook model for ${getNotebookLabel(panel)}`);
        return [];
      }

      const indices: number[] = [];

      for (let index = 0; index < model.cells.length; index += 1) {
        const cell = model.cells.get(index);

        if (cell.type !== 'code') {
          continue;
        }

        const autorunMetadata = cell.getMetadata(AUTORUN_METADATA_KEY);
        const tags = cell.getMetadata('tags');

        const shouldAutorun =
          autorunMetadata === true || hasAutorunTag(tags);

        if (shouldAutorun) {
          indices.push(index);
        }
      }

      console.info(
        `[${PLUGIN_ID}] ${getNotebookLabel(panel)} autorun cell indices:`,
        indices
      );

      return indices;
    };

    const ensureKernelReady = async (panel: NotebookPanel): Promise<boolean> => {
      const { sessionContext } = panel;

      console.info(
        `[${PLUGIN_ID}] waiting for existing session startup for ${getNotebookLabel(panel)}`
      );
      await sessionContext.ready;

      const hasKernel = !!sessionContext.session?.kernel;
      console.info(
        `[${PLUGIN_ID}] kernel ready for ${getNotebookLabel(panel)}: ${hasKernel}`
      );

      return hasKernel;
    };

    const runAutorunCells = async (panel: NotebookPanel): Promise<void> => {
      if (completed.has(panel)) {
        console.info(`[${PLUGIN_ID}] already completed for ${getNotebookLabel(panel)}`);
        return;
      }

      const existingTask = running.get(panel);
      if (existingTask) {
        console.info(`[${PLUGIN_ID}] already running for ${getNotebookLabel(panel)}`);
        await existingTask;
        return;
      }

      const task = (async () => {
        const notebookLabel = getNotebookLabel(panel);

        console.info(`[${PLUGIN_ID}] waiting for notebook to be ready: ${notebookLabel}`);

        await panel.context.ready;
        await panel.revealed;

        const hasKernel = await ensureKernelReady(panel);
        if (!hasKernel) {
          console.warn(`[${PLUGIN_ID}] no kernel available for ${notebookLabel}`);
          return;
        }

        const indices = getAutorunIndices(panel);
        completed.add(panel);

        if (!indices.length) {
          console.info(`[${PLUGIN_ID}] no autorun cells found in ${notebookLabel}`);
          return;
        }

        const notebook = panel.content;
        const previousActiveCellIndex = notebook.activeCellIndex;

        try {
          for (const index of indices) {
            console.info(
              `[${PLUGIN_ID}] running autorun cell ${index} in ${notebookLabel}`
            );
            notebook.activeCellIndex = index;
            await NotebookActions.run(notebook, panel.sessionContext, sessionDialogs);
          }

          console.info(`[${PLUGIN_ID}] completed autorun for ${notebookLabel}`);
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
      console.info(`[${PLUGIN_ID}] scheduling notebook: ${getNotebookLabel(panel)}`);
      void runAutorunCells(panel).catch(error => {
        console.error(
          `[${PLUGIN_ID}] autorun failed for ${getNotebookLabel(panel)}`,
          error
        );
      });
    };

    tracker.widgetAdded.connect((_, panel) => {
      console.info(`[${PLUGIN_ID}] widget added: ${getNotebookLabel(panel)}`);
      registerPanel(panel);
    });

    tracker.forEach(panel => {
      registerPanel(panel);
    });
  }
};

export default plugin;