// electron-builder afterPack hook.
// We have no Apple developer certificate, so give the finished macOS app an
// ad-hoc signature: Apple Silicon Macs refuse to launch apps with no signature at all.
const { execFileSync } = require('child_process');
const path = require('path');

exports.default = async function (context) {
  if (context.electronPlatformName !== 'darwin') return;
  // universal builds pack x64 and arm64 into temp folders first; only sign the merged app
  if (/-temp$/.test(context.appOutDir)) return;
  const app = path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`);
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', app], { stdio: 'inherit' });
};
