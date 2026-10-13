# MediHisaab Frontend

Standard React + TypeScript + Vite frontend application for **MediHisaab** (Pharmacy software for Indian medical stores).

## Tech Stack

- **React 19**
- **TypeScript**
- **Vite**
- **React Router DOM 7**
- **Tailwind CSS v4**
- **Lucide Icons & Radix UI**
- **Sonner** (notifications)

## Getting Started

### Prerequisites

- Node.js (v18+)
- npm (v9+)

### Installation

```bash
npm install
```

### Development Server

Start the local Vite development server:

```bash
npm run dev
```

The application will be accessible at `http://localhost:5173`.

### Production Build

Typecheck and generate the production bundle into `dist/`:

```bash
npm run build
```

Preview the production build locally:

```bash
npm run preview
```

### Testing & Linting

Run automated unit and routing tests:

```bash
npm test
```

Run ESLint checks:

```bash
npm run lint
```

Format code with Prettier:

```bash
npm run format
```

## Routing & Pages

All pages and layouts are built with standard React Router DOM and render independently in demo mode:

| Path            | Description                                                             |
| --------------- | ----------------------------------------------------------------------- |
| `/`             | Landing page with product overview, daily timeline, and concept mockups |
| `/product`      | Product details, billing, inventory, batch & expiry workflows           |
| `/how-it-works` | Step-by-step setup journey and credential separation guide              |
| `/plans`        | Pricing tiers, trial details, and license renewal explanations          |
| `/account`      | Sign-in and pharmacy registration forms with demo authentication        |
| `/client`       | Client dashboard (overview, download, renewal simulation, activity)     |
| `/download`     | Gated Windows installer download and system requirements                |
| `/about`        | Background and philosophy behind MediHisaab                             |
| `/support`      | Help guides, common troubleshooting, and demo support form              |
| `/privacy`      | Privacy draft disclosures                                               |
| `/faq`          | Accordion FAQ covering offline mode, licensing, backups, etc.           |
| `*`             | 404 Not Found page with return-to-home navigation                       |

## Deployment Requirements (SPA Fallback)

Because this application uses client-side routing via React Router DOM, direct visits to deep links (such as `/product`, `/account`, `/client`) or hard browser refreshes require the hosting server to rewrite non-static asset requests to `index.html`.

### Configuration Examples

- **Netlify**: Place a `_redirects` file in `public/`:
  ```text
  /*    /index.html   200
  ```
- **Vercel**: In `vercel.json`:
  ```json
  {
    "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
  }
  ```
- **Nginx**:
  ```nginx
  location / {
    try_files $uri $uri/ /index.html;
  }
  ```
- **Apache**: In `.htaccess`:
  ```apache
  RewriteEngine On
  RewriteBase /
  RewriteRule ^index\.html$ - [L]
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
  ```
- **Cloudflare Pages / GitHub Pages**: Ensure single-page application redirection is configured or `index.html` is used as the 404 fallback.
