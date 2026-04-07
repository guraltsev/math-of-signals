const { INotebookTracker, NotebookActions } = require('@jupyterlab/notebook');

const PLUGIN_ID = 'math-of-signals-autorun:plugin';
const AUTORUN_METADATA_KEY = 'autorun';
const PENDING_KERNEL_STATUSES = new Set([
  'initializing',
  'starting',
  'restarting',
  'autorestarting'
]);

function getAutorunCells(panel) {
  const cells = [];
  for (const cell of panel.content.widgets) {
    if (cell?.model?.type !== 'code') {
      continue;
    }
    if (cell.model.metadata?.get(AUTORUN_METADATA_KEY) === true) {
      cells.push(cell);
    }
  }
  return cells;
}

async function waitForKernelReady(sessionContext) {
  await sessionContext.ready;

  if (!sessionContext.session?.kernel) {
    return false;
  }

  if (!PENDING_KERNEL_STATUSES.has(sessionContext.kernelDisplayStatus)) {
    return true;
  }

  await new Promise(resolve => {
    const onStatusChanged = () => {
      const displayStatus = sessionContext.kernelDisplayStatus;
      if (displayStatus && !PENDING_KERNEL_STATUSES.has(displayStatus)) {
        sessionContext.statusChanged.disconnect(onStatusChanged);
        sessionContext.connectionStatusChanged.disconnect(onStatusChanged);
        resolve();
      }
    };

    sessionContext.statusChanged.connect(onStatusChanged);
    sessionContext.connectionStatusChanged.connect(onStatusChanged);
    onStatusChanged();
  });

  return !!sessionContext.session?.kernel;
}

async function autorunNotebook(panel) {
  await Promise.all([panel.revealed, panel.context.ready, panel.sessionContext.ready]);

  const kernelReady = await waitForKernelReady(panel.sessionContext);
  if (!kernelReady) {
    return;
  }

  const autorunCells = getAutorunCells(panel);
  if (!autorunCells.length) {
    return;
  }

  await NotebookActions.runCells(panel.content, autorunCells, panel.sessionContext);
}

const plugin = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [INotebookTracker],
  activate: (_app, tracker) => {
    const scheduledPanels = new WeakSet();

    const schedule = panel => {
      if (!panel || scheduledPanels.has(panel)) {
        return;
      }
      scheduledPanels.add(panel);
      void autorunNotebook(panel).catch(error => {
        console.error(`[${PLUGIN_ID}] autorun failed`, error);
      });
    };

    if (tracker.currentWidget) {
      schedule(tracker.currentWidget);
    }

    tracker.widgetAdded.connect((_sender, panel) => {
      schedule(panel);
    });
  }
};

module.exports = plugin;
module.exports.default = plugin;
