import { Link, useParams } from "react-router-dom";
import { ScrollyStory } from "../components/ScrollyStory";
import { getStory } from "../stories/fixtures";

export function StoryPage() {
  const { slug = "" } = useParams();
  const story = getStory(slug);

  if (!story) {
    return (
      <div className="page">
        <h1 className="page__title">Story not found</h1>
        <p className="page__lede">No narrative is registered for “{slug}”.</p>
        <Link className="btn btn--ghost" to="/stories">
          Back to stories
        </Link>
      </div>
    );
  }

  return (
    <div className="page page--story">
      <ScrollyStory story={story} />
    </div>
  );
}
