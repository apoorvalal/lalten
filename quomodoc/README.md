# Quomodoc

Quomodoc hosts arbitrary HTML documents in a script-disabled iframe and lets readers attach comments to highlighted text.

The application shell uses a locally hosted IBM Plex Sans WOFF2 asset, so its
typography does not depend on client-installed fonts or a third-party font CDN.

## Routes

- `GET /quomodoc/` — document index and browser upload form
- `GET /quomodoc/docs/<slug>` — annotation workspace
- `GET /quomodoc/raw/<slug>` — stable, distraction-free HTML view
- `POST /quomodoc/api/documents` — password-protected JSON or multipart upload
- `GET /quomodoc/cli` — download the zero-dependency interactive upload CLI
- `GET /quomodoc/api/documents` — document listing
- `POST /quomodoc/api/documents/<slug>/comments` — add an anchored comment
- `POST /quomodoc/api/comments/<id>/replies` — reply to a comment
- `POST /quomodoc/api/comments/<id>/resolve` — resolve or reopen a comment
- `GET /quomodoc/health` — health check

JSON upload shape:

```json
{
  "password": "<upload password>",
  "title": "Document title",
  "slug": "optional-slug",
  "html": "<!doctype html>..."
}
```

The service stores only the SHA-256 verifier in `/etc/quomodoc.env`; plaintext is not persisted. Set it interactively with `python set_password.py` and restart the service.

The downloadable CLI accepts a local HTML path, prompts for the upload password
without putting it in shell history or process arguments, and writes through the
HTTPS API. Uploading an existing slug replaces that document while preserving
its comments. Quomodoc re-anchors comments by their quoted text and surrounding
context; comments that can no longer be located are retained and marked as
needing re-anchoring. Quomodoc intentionally exposes no delete endpoint.

Uploaded scripts are disabled by iframe sandboxing and Content Security Policy.
Styles from inline blocks, self-contained `data:` stylesheets, and HTTPS-hosted
assets remain available. The CSP makes a narrow exception for the audited KaTeX
0.16.22 bundle and Quarto renderer hashes used by the current self-contained
paper export; other uploaded JavaScript remains blocked.
