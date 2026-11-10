const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pup', {
  onUpdate: (fn) => ipcRenderer.on('pup', (_e, data) => fn(data)),
  ignoreMouse: (ignore) => ipcRenderer.send('ignore-mouse', ignore),
  pet: () => ipcRenderer.send('pet'),
  menu: () => ipcRenderer.send('menu'),
  dragStart: () => ipcRenderer.send('drag-start'),
  dragEnd: () => ipcRenderer.send('drag-end'),
});
