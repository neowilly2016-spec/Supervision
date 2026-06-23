import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NavigationMenu from './NavigationMenu';
import './App.css';

// Import page components
import Dashboard from './pages/Dashboard';
import AutoDiscovery from './pages/AutoDiscovery';
import NetworkScan from './pages/NetworkScan';
import Topology from './pages/Topology';
import DeviceList from './pages/DeviceList';
import Performance from './pages/Performance';
import Alerts from './pages/Alerts';
import HealthStatus from './pages/HealthStatus';
import AllDevices from './pages/AllDevices';
import BackboneRouters from './pages/BackboneRouters';
import MBHDevices from './pages/MBHDevices';
import DeviceDetails from './pages/DeviceDetails';
import InterfaceList from './pages/InterfaceList';
import OpticalMetrics from './pages/OpticalMetrics';
import Utilization from './pages/Utilization';
import Errors from './pages/Errors';
import BGP from './pages/BGP';
import OSPF from './pages/OSPF';
import ISIS from './pages/ISIS';
import MPLS from './pages/MPLS';
import MPLSTETunnels from './pages/MPLSTETunnels';
import LSPStatus from './pages/LSPStatus';
import RSVP from './pages/RSVP';
import TrafficEngineering from './pages/TrafficEngineering';
import BGPPeers from './pages/BGPPeers';
import BGPSessions from './pages/BGPSessions';
import RouteTables from './pages/RouteTables';
import ASPath from './pages/ASPath';
import SLAMonitoring from './pages/SLAMonitoring';
import Latency from './pages/Latency';
import Jitter from './pages/Jitter';
import PacketLoss from './pages/PacketLoss';
import Hardware from './pages/Hardware';
import SoftwareVersion from './pages/SoftwareVersion';
import Licenses from './pages/Licenses';
import AssetManagement from './pages/AssetManagement';
import Users from './pages/Users';
import Settings from './pages/Settings';
import SNMPConfig from './pages/SNMPConfig';
import Logs from './pages/Logs';

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <NavigationMenu />
        <main className="main-content">
          <Routes>
            {/* Dashboard */}
            <Route path="/" element={<Dashboard />} />
            
            {/* Discovery Routes */}
            <Route path="/discovery/auto" element={<AutoDiscovery />} />
            <Route path="/discovery/scan" element={<NetworkScan />} />
            <Route path="/discovery/topology" element={<Topology />} />
            <Route path="/discovery/devices" element={<DeviceList />} />
            
            {/* Monitoring Routes */}
            <Route path="/monitoring/dashboard" element={<Dashboard />} />
            <Route path="/monitoring/performance" element={<Performance />} />
            <Route path="/monitoring/alerts" element={<Alerts />} />
            <Route path="/monitoring/health" element={<HealthStatus />} />
            
            {/* Devices Routes */}
            <Route path="/devices" element={<AllDevices />} />
            <Route path="/devices/backbone" element={<BackboneRouters />} />
            <Route path="/devices/mbh" element={<MBHDevices />} />
            <Route path="/devices/details" element={<DeviceDetails />} />
            
            {/* Interfaces Routes */}
            <Route path="/interfaces" element={<InterfaceList />} />
            <Route path="/interfaces/optical" element={<OpticalMetrics />} />
            <Route path="/interfaces/utilization" element={<Utilization />} />
            <Route path="/interfaces/errors" element={<Errors />} />
            
            {/* Protocols Routes */}
            <Route path="/protocols/bgp" element={<BGP />} />
            <Route path="/protocols/ospf" element={<OSPF />} />
            <Route path="/protocols/isis" element={<ISIS />} />
            <Route path="/protocols/mpls" element={<MPLS />} />
            
            {/* Traffic Engineering Routes */}
            <Route path="/te/tunnels" element={<MPLSTETunnels />} />
            <Route path="/te/lsp" element={<LSPStatus />} />
            <Route path="/te/rsvp" element={<RSVP />} />
            <Route path="/te/traffic" element={<TrafficEngineering />} />
            
            {/* BGP Routes */}
            <Route path="/bgp/peers" element={<BGPPeers />} />
            <Route path="/bgp/sessions" element={<BGPSessions />} />
            <Route path="/bgp/routes" element={<RouteTables />} />
            <Route path="/bgp/aspath" element={<ASPath />} />
            
            {/* SLA Routes */}
            <Route path="/sla" element={<SLAMonitoring />} />
            <Route path="/sla/latency" element={<Latency />} />
            <Route path="/sla/jitter" element={<Jitter />} />
            <Route path="/sla/packetloss" element={<PacketLoss />} />
            
            {/* Inventory Routes */}
            <Route path="/inventory/hardware" element={<Hardware />} />
            <Route path="/inventory/software" element={<SoftwareVersion />} />
            <Route path="/inventory/licenses" element={<Licenses />} />
            <Route path="/inventory/assets" element={<AssetManagement />} />
            
            {/* Admin Routes */}
            <Route path="/admin/users" element={<Users />} />
            <Route path="/admin/settings" element={<Settings />} />
            <Route path="/admin/snmp" element={<SNMPConfig />} />
            <Route path="/admin/logs" element={<Logs />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
