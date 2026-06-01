/* NIM // CANVAS — orchestrator. Phase: boot → canvas */
(function () {
  const { BootScreen, NimCanvas } = window;

  function App() {
    const [phase, setPhase] = React.useState('boot');

    const wake = React.useCallback(() => {
      document.body.setAttribute('data-phase', 'canvas');
      setPhase('canvas');
    }, []);

    React.useEffect(() => {
      document.body.setAttribute('data-phase', phase);
    }, [phase]);

    return (
      <div style={{ position: 'fixed', inset: 0, background: '#000', overflow: 'hidden' }}>
        {phase === 'boot'   && <BootScreen onWake={wake} />}
        {phase === 'canvas' && <NimCanvas />}
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById('root')).render(<App />);
})();
