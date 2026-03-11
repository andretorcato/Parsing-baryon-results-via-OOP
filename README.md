# parsing_baryon_results

This repository is configured to build Quarto documentation with GitHub Actions and publish the rendered site to GitHub Pages.

## Local build

Install [Quarto](https://quarto.org/) and run:

```bash
quarto preview
```

To produce the static site without preview:

```bash
quarto render
```

## GitHub Actions deployment

The workflow file is at `.github/workflows/quarto-publish.yml`.

It will:

1. Run on pushes to `main`
2. Render the Quarto site
3. Upload the generated `_site/` directory
4. Deploy it to GitHub Pages

## One-time GitHub setup

After pushing this repository to GitHub:

1. Open the repository settings
2. Go to `Pages`
3. Set the source to `GitHub Actions`

Once that is enabled, every push to `main` will publish the site.
