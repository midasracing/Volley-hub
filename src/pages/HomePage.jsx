import React from 'react';
import { dateKey, feedDateKey } from '../data.js';
import { NOW } from '../dateUtils.js';
import { FeedWarning, LoadingCards } from '../components/UiPrimitives.jsx';
import { MatchGroups } from '../components/MatchCards.jsx';

const HomePage = React.memo(function HomePage({ feeds, matches, loading, errors, refresh, logos }) {
  const allMatches = matches;
  const today = dateKey(NOW());
  const todayMatches = allMatches.filter(match => feedDateKey(match.date) === today);
  const upcoming = allMatches.filter(match => feedDateKey(match.date) >= today).slice(0, 3);
  const featured = todayMatches.length ? todayMatches : upcoming;
  return <>
    <FeedWarning errors={errors} refresh={refresh} />
    {loading && !Object.keys(feeds).length ? <LoadingCards /> : <MatchGroups compact matches={featured} logos={logos} emptyMessage="Nie mamy jeszcze zaplanowanych spotkań w pobranych danych." />}

  </>;
});
export default HomePage;
