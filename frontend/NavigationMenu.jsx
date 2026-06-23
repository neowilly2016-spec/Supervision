import React, { useState } from 'react';
import './NavigationMenu.css';

const NavigationMenu = () => {
  const [openMenu, setOpenMenu] = useState(null);

  const handleMouseEnter = (menu) => {
    setOpenMenu(menu);
  };

  const handleMouseLeave = () => {
    setOpenMenu(null);
  };

  const menuItems = [
    {
      title: 'Discovery',
      items: [
        { label: 'Auto Discovery', link: '/discovery/auto' },
        { label: 'Network Scan', link: '/discovery/scan' },
        { label: 'LLDP/CDP Topology', link: '/discovery/topology' },
        { label: 'Device List', link: '/discovery/devices' }
      ]
    },
    {
      title: 'Monitoring',
      items: [
        { label: 'Dashboard', link: '/monitoring/dashboard' },
        { label: 'Performance', link: '/monitoring/performance' },
        { label: 'Alerts', link: '/monitoring/alerts' },
        { label: 'Health Status', link: '/monitoring/health' }
      ]
    },
    {
      title: 'Devices',
      items: [
        { label: 'All Devices', link: '/devices' },
        { label: 'Backbone Routers', link: '/devices/backbone' },
        { label: 'MBH Devices', link: '/devices/mbh' },
        { label: 'Device Details', link: '/devices/details' }
      ]
    },
    {
      title: 'Interfaces',
      items: [
        { label: 'Interface List', link: '/interfaces' },
        { label: 'Optical Metrics', link: '/interfaces/optical' },
        { label: 'Utilization', link: '/interfaces/utilization' },
        { label: 'Errors', link: '/interfaces/errors' }
      ]
    },
    {
      title: 'Protocols',
      items: [
        { label: 'BGP', link: '/protocols/bgp' },
        { label: 'OSPF', link: '/protocols/ospf' },
        { label: 'ISIS', link: '/protocols/isis' },
        { label: 'MPLS', link: '/protocols/mpls' }
      ]
    },
    {
      title: 'TE',
      items: [
        { label: 'MPLS-TE Tunnels', link: '/te/tunnels' },
        { label: 'LSP Status', link: '/te/lsp' },
        { label: 'RSVP', link: '/te/rsvp' },
        { label: 'Traffic Engineering', link: '/te/traffic' }
      ]
    },
    {
      title: 'BGP',
      items: [
        { label: 'BGP Peers', link: '/bgp/peers' },
        { label: 'BGP Sessions', link: '/bgp/sessions' },
        { label: 'Route Tables', link: '/bgp/routes' },
        { label: 'AS Path', link: '/bgp/aspath' }
      ]
    },
    {
      title: 'SLA',
      items: [
        { label: 'SLA Monitoring', link: '/sla' },
        { label: 'Latency', link: '/sla/latency' },
        { label: 'Jitter', link: '/sla/jitter' },
        { label: 'Packet Loss', link: '/sla/loss' }
      ]
    },
    {
      title: 'Inventory',
      items: [
        { label: 'Hardware', link: '/inventory/hardware' },
        { label: 'Software Version', link: '/inventory/software' },
        { label: 'Licenses', link: '/inventory/licenses' },
        { label: 'Asset Management', link: '/inventory/assets' }
      ]
    },
    {
      title: 'Admin',
      items: [
        { label: 'Users', link: '/admin/users' },
        { label: 'Settings', link: '/admin/settings' },
        { label: 'SNMP Config', link: '/admin/snmp' },
        { label: 'Logs', link: '/admin/logs' }
      ]
    }
  ];

  return (
    <nav className="navigation-menu">
      <div className="nav-container">
        <div className="nav-logo">
          <h2>Network Supervision</h2>
        </div>
        <ul className="nav-items">
          {menuItems.map((menu, index) => (
            <li
              key={index}
              className="nav-item"
              onMouseEnter={() => handleMouseEnter(menu.title)}
              onMouseLeave={handleMouseLeave}
            >
              <button className="nav-button">
                {menu.title}
                <span className="dropdown-icon">▼</span>
              </button>
              {openMenu === menu.title && (
                <ul className="dropdown-menu">
                  {menu.items.map((item, idx) => (
                    <li key={idx} className="dropdown-item">
                      <a href={item.link}>{item.label}</a>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
};

export default NavigationMenu;
