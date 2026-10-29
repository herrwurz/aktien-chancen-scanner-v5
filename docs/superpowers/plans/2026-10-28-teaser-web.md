# Teaser web implementation plan

Goal: Existing browser UI with password-protected HTTPS, persistent case history and isolated Docker operation.
Architecture: Reuse FastAPI UI and journal; dedicated web factory protects all routes with HTTP Basic,
injects server-side research credentials, and owns a separate SQLite/data directory. Caddy handles TLS.
Constraints: No deployment, no existing services modified, no paid providers, no credentials in Git.

1. Test whole-app authentication, private token handling and cross-origin write rejection.
2. Implement web factory with mandatory secret files and separate state directory.
3. Add case history and robust analysis error feedback to existing template.
4. Add standalone compose/Caddy configuration and exact operator setup instructions.
5. Run regression suite, isolated container checks, then create separate PR.
