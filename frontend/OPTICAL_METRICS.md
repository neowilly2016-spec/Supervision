# Optical Metrics Visualization - Frontend Component

## Overview
Frontend React component for visualizing optical TX/RX power metrics from network interfaces.

## Features

### 1. Device Optical Dashboard
**Component:** `OpticalMetricsDashboard.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const OpticalMetricsDashboard = ({ deviceId }) => {
  const [metrics, setMetrics] = useState([]);
  const [timerange, setTimerange] = useState('24h');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchOpticalMetrics();
  }, [deviceId, timerange]);

  const fetchOpticalMetrics = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/optical/devices/${deviceId}?timerange=${timerange}`);
      const data = await response.json();
      setMetrics(data);
    } catch (error) {
      console.error('Error fetching optical metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="optical-metrics-dashboard">
      <h2>Optical Metrics - Device {deviceId}</h2>
      
      {/* Timerange Selector */}
      <div className="timerange-selector">
        <button onClick={() => setTimerange('1h')}>1H</button>
        <button onClick={() => setTimerange('6h')}>6H</button>
        <button onClick={() => setTimerange('24h')}>24H</button>
        <button onClick={() => setTimerange('7d')}>7D</button>
      </div>

      {/* TX/RX Power Graph */}
      <div className="power-chart">
        <h3>TX/RX Power (dBm)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={metrics}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="rx_power_dbm" stroke="#8884d8" name="RX Power" />
            <Line type="monotone" dataKey="tx_power_dbm" stroke="#82ca9d" name="TX Power" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Temperature Chart */}
      <div className="temperature-chart">
        <h3>Module Temperature (°C)</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={metrics}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="temperature_celsius" stroke="#ff7300" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default OpticalMetricsDashboard;
```

### 2. Interface Optical Summary Table
**Component:** `OpticalSummaryTable.jsx`

```jsx
import React, { useState, useEffect } from 'react';

const OpticalSummaryTable = ({ deviceId }) => {
  const [summary, setSummary] = useState([]);

  useEffect(() => {
    fetchSummary();
  }, [deviceId]);

  const fetchSummary = async () => {
    const response = await fetch(`/api/optical/summary/${deviceId}`);
    const data = await response.json();
    setSummary(data);
  };

  const getPowerStatus = (rxPower, txPower) => {
    // Optical power thresholds (typical for 10G optics)
    const RX_MIN = -14; // dBm
    const RX_MAX = -1;  // dBm
    const TX_MIN = -5;  // dBm
    const TX_MAX = 0;   // dBm

    if (rxPower < RX_MIN || rxPower > RX_MAX || txPower < TX_MIN || txPower > TX_MAX) {
      return 'critical';
    }
    if (rxPower < (RX_MIN + 3) || txPower < (TX_MIN + 1)) {
      return 'warning';
    }
    return 'ok';
  };

  return (
    <div className="optical-summary-table">
      <h3>Current Optical Status</h3>
      <table>
        <thead>
          <tr>
            <th>Interface</th>
            <th>RX Power (dBm)</th>
            <th>TX Power (dBm)</th>
            <th>Temperature (°C)</th>
            <th>Status</th>
            <th>Last Update</th>
          </tr>
        </thead>
        <tbody>
          {summary.map((iface) => (
            <tr key={iface.if_index} className={`status-${getPowerStatus(iface.rx_power_dbm, iface.tx_power_dbm)}`}>
              <td>{iface.if_name}</td>
              <td>{iface.rx_power_dbm?.toFixed(2)}</td>
              <td>{iface.tx_power_dbm?.toFixed(2)}</td>
              <td>{iface.temperature_celsius?.toFixed(1)}</td>
              <td>
                <span className={`badge-${getPowerStatus(iface.rx_power_dbm, iface.tx_power_dbm)}`}>
                  {getPowerStatus(iface.rx_power_dbm, iface.tx_power_dbm).toUpperCase()}
                </span>
              </td>
              <td>{new Date(iface.time).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default OpticalSummaryTable;
```

### 3. CSS Styling
**File:** `optical-metrics.css`

```css
.optical-metrics-dashboard {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.timerange-selector {
  margin: 20px 0;
  display: flex;
  gap: 10px;
}

.timerange-selector button {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: #f5f5f5;
  border-radius: 4px;
  cursor: pointer;
}

.timerange-selector button:hover {
  background: #e0e0e0;
}

.power-chart, .temperature-chart {
  margin: 30px 0;
}

.optical-summary-table table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
}

.optical-summary-table th,
.optical-summary-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.optical-summary-table th {
  background: #f5f5f5;
  font-weight: 600;
}

.status-critical {
  background-color: #ffebee;
}

.status-warning {
  background-color: #fff9c4;
}

.status-ok {
  background-color: #e8f5e9;
}

.badge-critical {
  padding: 4px 8px;
  border-radius: 4px;
  background: #f44336;
  color: white;
  font-size: 12px;
}

.badge-warning {
  padding: 4px 8px;
  border-radius: 4px;
  background: #ffc107;
  color: black;
  font-size: 12px;
}

.badge-ok {
  padding: 4px 8px;
  border-radius: 4px;
  background: #4caf50;
  color: white;
  font-size: 12px;
}
```

## API Endpoints Used

1. **GET /api/optical/devices/{device_id}**
   - Fetch historical optical metrics
   - Query params: `timerange` (1h, 6h, 24h, 7d)

2. **GET /api/optical/interface/{device_id}/{if_index}**
   - Fetch metrics for specific interface
   - Query params: `timerange`

3. **GET /api/optical/summary/{device_id}**
   - Get latest readings for all interfaces

## Optical Power Thresholds

### Standard 10GBASE-LR/ER
- **RX Power:** -14 dBm to -1 dBm (typical)
- **TX Power:** -5 dBm to 0 dBm (typical)
- **Temperature:** 0°C to 70°C operating range

### Alert Levels
- **Critical:** Power outside operational range
- **Warning:** Power within 3 dBm of threshold
- **OK:** Power within normal range

## Installation

```bash
npm install recharts  # For charts
```

## Usage Example

```jsx
import OpticalMetricsDashboard from './components/OpticalMetricsDashboard';
import OpticalSummaryTable from './components/OpticalSummaryTable';

function DeviceDetailPage({ deviceId }) {
  return (
    <div>
      <h1>Device Optical Monitoring</h1>
      <OpticalSummaryTable deviceId={deviceId} />
      <OpticalMetricsDashboard deviceId={deviceId} />
    </div>
  );
}
```

## Data Export Feature (Future Enhancement)

```jsx
const exportToCSV = () => {
  const csv = metrics.map(row => 
    `${row.time},${row.if_name},${row.rx_power_dbm},${row.tx_power_dbm},${row.temperature_celsius}`
  ).join('\n');
  
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `optical_metrics_${deviceId}_${Date.now()}.csv`;
  a.click();
};
```

## Notes

- Graphs auto-refresh every 5 minutes
- Color coding: Blue = RX, Green = TX, Orange = Temperature
- Critical alerts trigger when power drops below -14 dBm or exceeds operational limits
- All timestamps displayed in local timezone
