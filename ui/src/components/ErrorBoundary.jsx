import React from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Hexor UI Crash Caught by ErrorBoundary:", error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-full bg-[#040810] text-cyan-200 flex flex-col items-center justify-center p-6 font-mono-tech">
          <div className="max-w-md w-full bg-cyan-950/40 border border-red-500/50 rounded-2xl p-6 backdrop-blur-xl shadow-[0_0_30px_rgba(239,68,68,0.2)] text-center">
            <div className="w-12 h-12 rounded-full bg-red-950/60 border border-red-500 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-6 h-6 text-red-400 animate-pulse" />
            </div>
            <h2 className="font-orbitron text-lg font-bold text-red-300 tracking-wider mb-2">
              HEXOR SUBSYSTEM RECOVERY
            </h2>
            <p className="text-xs text-cyan-400/80 mb-4 leading-relaxed">
              A rendering exception was intercepted. Core diagnostics captured below.
            </p>
            <div className="bg-black/60 border border-red-500/30 rounded-lg p-3 text-left text-[11px] text-red-300 overflow-x-auto max-h-32 mb-4">
              {this.state.error?.toString() || "Unknown rendering exception"}
            </div>
            <button
              onClick={this.handleReload}
              className="w-full flex items-center justify-center space-x-2 py-2.5 bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 text-black font-orbitron font-bold text-xs rounded-xl transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)]"
            >
              <RotateCw className="w-4 h-4" />
              <span>RELOAD HEXOR CORES</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

