module.exports = {
  ci: {
    collect: {
      staticDistDir: './dist',
      isSinglePageApplication: true,
      url: ['http://localhost/'],
      numberOfRuns: 3,
      settings: {
        preset: 'desktop',
        onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
        chromeFlags: '--headless=new --no-sandbox --disable-dev-shm-usage'
      }
    },
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.9 }],
        'categories:accessibility': ['warn', { minScore: 0.9 }],
        'largest-contentful-paint': ['warn', { maxNumericValue: 2500 }],
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.1 }],
        'total-blocking-time': ['warn', { maxNumericValue: 300 }],
        interactive: ['warn', { maxNumericValue: 3500 }],
        'resource-summary:script:size': ['error', { maxNumericValue: 262144 }],
        'resource-summary:stylesheet:size': ['warn', { maxNumericValue: 81920 }]
      }
    },
    upload: {
      target: 'filesystem',
      outputDir: '../.lighthouseci'
    }
  }
}

