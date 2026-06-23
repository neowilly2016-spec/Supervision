# Navigation Menu Integration Guide

## Overview
This guide explains how to integrate the NavigationMenu component into your Network Supervision application.

## Files Included
- `NavigationMenu.jsx` - React component for the navigation menu
- `NavigationMenu.css` - Stylesheet with responsive design and hover effects

## Quick Start

### 1. Create Main Application File
Create `src/App.jsx` (if not exists):

```jsx
import React from 'react';
import NavigationMenu from './NavigationMenu';
import './App.css';

function App() {
  return (
    <div className="app">
      <NavigationMenu />
      <main className="main-content">
        {/* Your main content goes here */}
        <h1>Network Supervision Dashboard</h1>
        <p>Select a menu item to navigate.</p>
      </main>
    </div>
  );
}

export default App;
```

### 2. Add Basic App Styling
Create `src/App.css`:

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.app {
  min-height: 100vh;
  background: #f5f7fa;
}

.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 40px 20px;
}

.main-content h1 {
  color: #2c3e50;
  margin-bottom: 20px;
}
```

### 3. Setup Entry Point
Update `src/index.js` or `src/main.jsx`:

```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### 4. Add React Router (Optional but Recommended)
For actual navigation functionality:

```bash
npm install react-router-dom
```

Update `App.jsx` with routing:

```jsx
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NavigationMenu from './NavigationMenu';

// Import your page components
import Dashboard from './pages/Dashboard';
import DeviceList from './pages/DeviceList';
import OpticalMetrics from './pages/OpticalMetrics';
// ... other pages

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <NavigationMenu />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/discovery/auto" element={<AutoDiscovery />} />
            <Route path="/devices" element={<DeviceList />} />
            <Route path="/interfaces/optical" element={<OpticalMetrics />} />
            {/* Add routes for other menu items */}
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
```

## Menu Structure

The NavigationMenu includes 10 main sections:

1. **Discovery** - Auto Discovery, Network Scan, LLDP/CDP Topology, Device List
2. **Monitoring** - Dashboard, Performance, Alerts, Health Status
3. **Devices** - All Devices, Backbone Routers, MBH Devices, Device Details
4. **Interfaces** - Interface List, Optical Metrics, Utilization, Errors
5. **Protocols** - BGP, OSPF, ISIS, MPLS
6. **TE** - MPLS-TE Tunnels, LSP Status, RSVP, Traffic Engineering
7. **BGP** - BGP Peers, BGP Sessions, Route Tables, AS Path
8. **SLA** - SLA Monitoring, Latency, Jitter, Packet Loss
9. **Inventory** - Hardware, Software Version, Licenses, Asset Management
10. **Admin** - Users, Settings, SNMP Config, Logs

## Customization

### Update Menu Links
Edit `NavigationMenu.jsx` and modify the `menuItems` array:

```jsx
const menuItems = [
  {
    title: 'Discovery',
    items: [
      { label: 'Auto Discovery', link: '/discovery/auto' },
      // ... your custom links
    ]
  },
  // ... other menu items
];
```

### Customize Colors
Edit `NavigationMenu.css` to change the theme:

```css
/* Change navigation background gradient */
.navigation-menu {
  background: linear-gradient(135deg, #1a252f 0%, #2c3e50 100%);
}

/* Change hover accent color */
.nav-button:hover {
  color: #e74c3c; /* Change from default #3498db */
}

.dropdown-item a:hover {
  background: #e74c3c; /* Match your accent color */
}
```

## Testing

1. Start your development server:
```bash
npm start
# or
npm run dev
```

2. Open browser to `http://localhost:3000`
3. Hover over menu items to see dropdowns
4. Test responsive behavior by resizing browser window

## Responsive Breakpoints

- **Desktop**: > 1200px - Full menu with all features
- **Tablet**: 768px - 1200px - Adjusted padding and spacing
- **Mobile**: < 768px - Stacked layout, smaller buttons

## Browser Support

- Chrome/Edge: ✓ Full support
- Firefox: ✓ Full support
- Safari: ✓ Full support
- Mobile browsers: ✓ Full support with touch interactions

## Next Steps

1. Create page components for each menu route
2. Connect navigation to your backend API endpoints
3. Add active state highlighting based on current route
4. Implement authentication/authorization for Admin section
5. Add breadcrumb navigation for deeper page hierarchies

## Support

For issues or questions:
- Check component code in `NavigationMenu.jsx`
- Review styling in `NavigationMenu.css`
- Refer to React Router documentation for routing setup
