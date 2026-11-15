"use strict";

const SUPABASE_URL =
    "https://lcqaabulzivfbyzbubox.supabase.co";

const SUPABASE_KEY =
    "sb_publishable_RgPwDES1XHJszD4c-9vQfA_V4rb_qhL";

const statsHeaders = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json"
};

async function loadVideoStats() {
    const cards = Array.from(
        document.querySelectorAll(
            ".event-card[data-event-id]"
        )
    );

    const eventIds = cards.map(
        card => card.dataset.eventId
    );

    if (!eventIds.length) {
        return;
    }

    const params = new URLSearchParams();

    params.set(
        "select",
        "event_id,views,likes"
    );

    params.set(
        "event_id",
        `in.(${eventIds.join(",")})`
    );

    try {
        const response = await fetch(
            `${SUPABASE_URL}/rest/v1/video_stats?${params}`,
            {
                headers: statsHeaders
            }
        );

        if (!response.ok) {
            throw new Error(
                `Stats request failed: ${response.status}`
            );
        }

        const rows = await response.json();

        const statsByEvent = new Map(
            rows.map(
                row => [row.event_id, row]
            )
        );

        cards.forEach(card => {
            const eventId =
                card.dataset.eventId;

            const stats =
                statsByEvent.get(eventId) || {
                    views: 0,
                    likes: 0
                };

            card.querySelector(
                ".view-count"
            ).textContent = stats.views;

            card.querySelector(
                ".like-count"
            ).textContent = stats.likes;
        });

    } catch (error) {
        console.error(
            "Unable to load SquirrelCam stats:",
            error
        );
    }
}

async function incrementStat(
    functionName,
    eventId
) {
    const response = await fetch(
        `${SUPABASE_URL}/rest/v1/rpc/${functionName}`,
        {
            method: "POST",
            headers: statsHeaders,
            body: JSON.stringify({
                p_event_id: eventId
            })
        }
    );

    if (!response.ok) {
        throw new Error(
            `${functionName} failed: ${response.status}`
        );
    }
}

document.querySelectorAll(
    ".event-card[data-event-id]"
).forEach(card => {
    const eventId = card.dataset.eventId;

    const likeButton =
        card.querySelector(".like-button");

    const likeCount =
        card.querySelector(".like-count");

    const viewCount =
        card.querySelector(".view-count");

    const likedKey =
        `squirrelcam-liked-${eventId}`;

    if (localStorage.getItem(likedKey)) {
        likeButton.disabled = true;
        likeButton.title =
            "You liked this event";
    }

    likeButton.addEventListener(
        "click",
        async () => {
            if (localStorage.getItem(likedKey)) {
                return;
            }

            likeButton.disabled = true;

            try {
                await incrementStat(
                    "increment_video_like",
                    eventId
                );

                likeCount.textContent =
                    Number(likeCount.textContent || 0) + 1;

                localStorage.setItem(
                    likedKey,
                    "true"
                );

                                likeButton.title =
                    "You liked this event";

            } catch (error) {
                likeButton.disabled = false;

                console.error(
                    "Unable to save like:",
                    error
                );
            }
        }
    );

    card.querySelectorAll("video").forEach(
        video => {
            video.addEventListener(
                "play",
                async () => {
                    const viewedKey =
                        `squirrelcam-viewed-${eventId}`;

                    if (
                        sessionStorage.getItem(viewedKey)
                    ) {
                        return;
                    }

                    sessionStorage.setItem(
                        viewedKey,
                        "true"
                    );

                    try {
                        await incrementStat(
                            "increment_video_view",
                            eventId
                        );

                        viewCount.textContent =
                            Number(
                                viewCount.textContent || 0
                            ) + 1;

                    } catch (error) {
                        sessionStorage.removeItem(
                            viewedKey
                        );

                        console.error(
                            "Unable to save view:",
                            error
                        );
                    }
                }
            );
        }
    );
});

loadVideoStats();
