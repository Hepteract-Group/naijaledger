import { Link } from "react-router-dom";
import { listStories } from "../stories/fixtures";

export function StoriesIndexPage() {
  const stories = listStories();

  return (
    <div className="page">
      <h1 className="page__title">Stories</h1>
      <p className="page__lede">
        Cited narrative investigations. Demo stories are labelled until human-approved publication
        is wired.
      </p>
      <ul className="story-index">
        {stories.map((story) => (
          <li key={story.slug} className="story-index__item">
            <Link className="story-index__link" to={`/stories/${story.slug}`}>
              <span className="story-index__title">{story.title}</span>
              {story.demo ? <span className="story-index__badge">Demo</span> : null}
            </Link>
            <p className="story-index__lede">{story.lede}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
