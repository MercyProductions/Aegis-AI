const cp = require('child_process');

function quoteForCmd(value) {
  const text = String(value);
  const escaped = text
    .replace(/\^/g, '^^')
    .replace(/%/g, '^%')
    .replace(/"/g, '""');
  if (!/[\s&()<>|^"%]/.test(text)) {
    return escaped;
  }
  return `"${escaped}"`;
}

function runCommand(command, args, options = {}) {
  const runner = process.platform === 'win32' ? process.env.ComSpec || 'cmd.exe' : command;
  const runnerArgs = process.platform === 'win32'
    ? ['/d', '/s', '/c', [command, ...args].map(quoteForCmd).join(' ')]
    : args;
  const result = cp.spawnSync(runner, runnerArgs, {
    cwd: options.cwd || process.cwd(),
    stdio: options.stdio || 'inherit',
    windowsHide: true
  });

  if (result.error) {
    console.error(`Failed to run ${command}: ${result.error.message}`);
    if (options.errorHint) {
      console.error(options.errorHint);
    }
    process.exit(1);
  }

  if (result.signal) {
    console.error(`${command} exited with signal ${result.signal}.`);
    process.exit(1);
  }

  if (typeof result.status === 'number' && result.status !== 0) {
    process.exit(result.status);
  }
}

module.exports = { quoteForCmd, runCommand };
