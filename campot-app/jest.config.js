module.exports = {
  testEnvironment: 'jsdom',
  clearMocks: true,
  globals: {
    structuredClone: (obj) => JSON.parse(JSON.stringify(obj))
  }
};
