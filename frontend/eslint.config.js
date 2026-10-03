// Project lint is oxlint (`yarn lint`). This flat config only lets a global ESLint parse TSX if one is invoked.
let tsParser = null;
let hooks = null;
for (const base of ["@typescript-eslint/parser", "/usr/lib/node_modules/@typescript-eslint/parser/dist/index.js"]) {
  try { tsParser = (await import(base)).default; break; } catch { /* not installed here */ }
}
for (const base of ["eslint-plugin-react-hooks", "/usr/lib/node_modules/eslint-plugin-react-hooks/index.js"]) {
  try { hooks = (await import(base)).default; break; } catch { /* not installed here */ }
}

export default [
  { ignores: ["dist/**", "node_modules/**", "src/components/ui/**", "src/lib/lucide-react.tsx", "src/lib/recharts.tsx"] },
  ...(tsParser
    ? [{
        files: ["src/**/*.{ts,tsx}"],
        languageOptions: { parser: tsParser, parserOptions: { ecmaFeatures: { jsx: true } } },
        plugins: hooks ? { "react-hooks": hooks } : {},
        rules: hooks ? { "react-hooks/rules-of-hooks": "error" } : {},
      }]
    : [{ ignores: ["**/*.ts", "**/*.tsx"] }]),
];
