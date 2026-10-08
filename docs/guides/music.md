# Music without claims

!!! warning "Not legal advice"
    This page summarises how platforms behave as of 2026. Check the license of anything you
    play, and the rules of each platform you stream to.

## Three separate risks

| Risk | Who | What happens |
| --- | --- | --- |
| **DMCA takedown** | Twitch, on a rights holder's request | VOD and clips deleted; repeated strikes can ban the channel |
| **Content ID claim** | YouTube, automatically | VOD demonetised, muted or blocked in some countries |
| **Terms of service** | Spotify, Deezer, Apple Music… | Their terms forbid public broadcast, *whatever the track's license* |

The last one surprises people: a royalty-free track played *from Spotify* is still a breach of
Spotify's terms, because the license you have with Spotify is personal listening. The risk
there is your Spotify account, not your channel.

## What is safe

- **Music cleared for streaming and absent from Content ID.** For example
  [StreamBeats](https://www.streambeats.com/) by Harris Heller, made for streamers and not
  registered in Content ID, so YouTube VODs are not claimed either.
- **Played from local files** you downloaded, through OBS (a *Media Source* or VLC source) or
  any local player. That avoids streaming services' terms entirely.

## What looks safe and is not

- **"No Copyright Sounds" (NCS)**: free to use with credit, but registered in Content ID, so
  YouTube VODs get claims anyway.
- **Mainstream tracks "for a few seconds"**: there is no safe duration.
- **"Royalty-free" playlists on Spotify**: the tracks may be cleared; playing them from Spotify
  on stream is not.

## Keep music out of the VOD anyway

Even with cleared music, separating it costs nothing and protects your VODs if a license
changes: put music on its own sink and leave it off the VOD track.
→ [Audio routing](audio.md#4-keep-the-music-out-of-your-vods-twitch)
