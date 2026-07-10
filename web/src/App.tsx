import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage } from "./pages/HomePage";
import { SourceDetailPage } from "./pages/SourceDetailPage";
import { SourcesIndexPage } from "./pages/SourcesIndexPage";
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
          <Route path="sources" element={<SourcesIndexPage />} />
          <Route path="sources/:id" element={<SourceDetailPage />} />
          <Route path="status" element={<StatusPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
