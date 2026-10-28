import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // Let the dev server read the team's fixtures (read-only) next to this folder.
    fs: { allow: ['.', '../fixtures'] },
  },
});
