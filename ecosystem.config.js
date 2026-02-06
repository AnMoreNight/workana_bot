// PM2 Ecosystem Configuration for Workana Scraper
module.exports = {
  apps: [{
    name: 'workana-scraper',
    script: 'main.py',
    interpreter: 'venv/bin/python',
    cwd: '/opt/workana-scraper',  // Change to your project path
    instances: 1,
    exec_mode: 'fork',
    
    // Auto-restart settings
    autorestart: true,
    watch: false,
    max_memory_restart: '2G',
    
    // Logging
    error_file: './logs/pm2-error.log',
    out_file: './logs/pm2-out.log',
    log_file: './logs/pm2-combined.log',
    time: true,
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
    
    // Environment variables
    env: {
      NODE_ENV: 'production',
      PYTHONUNBUFFERED: '1',  // Ensure Python output is unbuffered
    },
    
    // Environment-specific configs
    env_production: {
      NODE_ENV: 'production',
      PYTHONUNBUFFERED: '1',
    },
    
    // Restart delay
    min_uptime: '10s',
    max_restarts: 10,
    restart_delay: 4000,
    
    // Kill timeout (give time for graceful shutdown)
    kill_timeout: 5000,
    
    // Resource limits
    max_memory_restart: '2G',
    
    // Ignore file changes (don't restart on file changes)
    ignore_watch: [
      'node_modules',
      'logs',
      '*.db',
      '*.log',
      '.git',
      'venv',
      '__pycache__',
    ],
  }]
};

