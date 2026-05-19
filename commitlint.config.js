/** @type {import('@commitlint/types').UserConfig} */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [
      2,
      'always',
      [
        'agent',
        'api',
        'web',
        'schemas',
        'tools',
        'domain',
        'simulation',
        'optimization',
        'prediction',
        'memory',
        'state',
        'infra',
        'data',
        'docs',
        'ci',
        'deps',
      ],
    ],
    'scope-empty': [2, 'never'],
  },
};
