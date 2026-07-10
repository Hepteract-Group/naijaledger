import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage } from "./pages/HomePage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { StatusPage } from "./pages/StatusPage";
import { StoriesIndexPage } from "./pages/StoriesIndexPage";
import { StoryPage } from "./pages/StoryPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="explore" element={<ExplorePage />} />
          <Route path="stories" element={<StoriesIndexPage />} />
          <Route path="stories/:slug" element={<StoryPage />} />
          <Route
            path="sources"
            element={
              <PlaceholderPage
                title="Sources"
                lede="Browse the public source registry and drill into archived documents."
                next="E10.3 / E10.6"
              />
            }
          />
          <Route path="status" element={<StatusPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
