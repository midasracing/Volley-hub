import test from 'node:test';
import assert from 'node:assert/strict';
import { broadcastLinks } from '../src/broadcasts.js';
import { flattenFeed, matchesFromFeeds } from '../src/data.js';

test('a TV marker or channel name cannot invent a stream link', () => {
  assert.deepEqual(broadcastLinks({ broadcast: ['TV'] }), []);
  assert.deepEqual(broadcastLinks({ broadcast: ['Polsat Sport'] }), []);
});

test('only canonical video links become clickable and duplicates are removed', () => {
  const url = 'https://www.youtube.com/watch?v=38BPqJpf0HU';
  assert.deepEqual(broadcastLinks({ broadcast_urls: [url, url, 'javascript:alert(1)',
    'https://www.youtube.com.evil.test/watch?v=38BPqJpf0HU', null] }), [url]);
});

test('second-league video links survive flattening and the match view', () => {
  const url = 'https://www.youtube.com/watch?v=nDOImTNf7_o';
  const feed = flattenFeed({ groups: [{ name: 'Grupa 4', matches: [{ id: '2561987',
    date: '07.11.2026', time: '17:00', home: 'Żychlin', away: 'Belsk Duży',
    status: 'scheduled', broadcast_urls: [url] }] }] }, 'second');
  assert.deepEqual(broadcastLinks(matchesFromFeeds({ second: feed })[0]), [url]);
});
