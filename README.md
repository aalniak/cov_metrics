# Covariance Viewer

This folder now includes a static image browser that is ready to publish with GitHub Pages.
The viewer is organized around `./new_data`, and only image files discovered under that tree are indexed.

## What it does

- shows a clean folder selector for each image directory
- lists the images in the selected folder
- supports searching by filename
- opens any image in a fullscreen lightbox
- works as a plain static site with no build step

## Files

- `index.html`: page structure
- `styles.css`: visual design and responsive layout
- `app.js`: folder selection, filtering, hash routing, and lightbox behavior
- `manifest.json`: generated list of image folders and files found under `new_data`
- `scripts/generate-manifest.ps1`: refreshes `manifest.json` from the `new_data` tree

## Refresh the gallery data

Run this whenever you add, remove, or rename files under `new_data`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate-manifest.ps1
```

That updates `manifest.json`, which is what the browser reads.
Each image-containing subfolder under `new_data` becomes its own gallery entry, so nested analysis outputs stay separated instead of being merged into one giant folder.

## Publish on GitHub Pages

1. Put this folder in a GitHub repository.
2. Commit the site files and the image folders.
3. Enable GitHub Pages for the repository using the repository root as the published source, or deploy the same static files with a Pages action.
4. Open the published site URL and the viewer will load `manifest.json` plus the folder images directly.

## Local preview

Because browsers block `fetch()` from `file://` pages, preview the site through a simple local static server instead of double-clicking `index.html`.
