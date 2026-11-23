# Bundled Autark packages

UrbanTrace's maps use [Autark](https://github.com/urban-toolkit/autark)'s `autk-map` and
`autk-core`. The features UrbanTrace needs are not in a published release yet, so this folder holds
packages built from a fork until they are:

| File | Package | Built from |
|---|---|---|
| `urban-toolkit-autk-map-4.1.1-67763d9.tgz` | `@urban-toolkit/autk-map` | [`ctsilva/autark`](https://github.com/ctsilva/autark) branch `fix/pointer-css-scale`, commit `67763d9` |
| `urban-toolkit-autk-core-4.1.1-67763d9.tgz` | `@urban-toolkit/autk-core` | the same commit |

What that branch adds over Autark 4.1.1, and where each part stands upstream:

- a hover event and `setTooltip` for the feature under the pointer:
  [urban-toolkit/autark#141](https://github.com/urban-toolkit/autark/pull/141) (open);
- pointer positions on a canvas under a CSS transform (React Flow zooms its nodes this way):
  [urban-toolkit/autark#148](https://github.com/urban-toolkit/autark/pull/148) (open).

`package.json` installs `autk-map` from its tarball and pins `autk-core` to the bundled one with
`overrides`. When a release of Autark includes these changes, replace both with the published
version and delete this folder.

To rebuild from an Autark checkout:

```sh
npm run build -w autk-core && npm run build -w autk-map
(cd autk-core && npm pack --pack-destination <urbantrace>/frontend/vendor)
(cd autk-map && npm pack --pack-destination <urbantrace>/frontend/vendor)
```

then rename the tarballs with the commit and update `package.json`.
