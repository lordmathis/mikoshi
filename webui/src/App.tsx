import { ChatView } from "./chat/chat-view.tsx";
import { needsOnboarding } from "./lib/native.ts";
import { OnboardingScreen } from "./onboarding-screen.tsx";

function App() {
  return needsOnboarding() ? <OnboardingScreen /> : <ChatView />;
}

export default App;
