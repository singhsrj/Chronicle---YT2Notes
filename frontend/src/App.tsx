import { SessionProvider } from './context';
import { Sidebar, MainContent } from './components';
import './styles/global.css';

function App() {
  return (
    <SessionProvider>
      <div className="app">
        <Sidebar />
        <MainContent />
      </div>
    </SessionProvider>
  );
}

export default App;
