module.exports = {
    testEnvironment: 'node',
    testMatch: ['**/tests/**/*.test.js'],
    collectCoverageFrom: [
        'electron_main.js',
        'gui/renderer.js'
    ],
    coverageDirectory: 'coverage',
    verbose: true
};
