"""
VibeDiff Gradio Battleground UI — v2 (Blind Evaluation)

Key principles:
  - Model names and prompts are HIDDEN from the evaluator (blind testing).
  - Competitors are labeled as "Response A", "Response B", etc.
  - The UI is a continuous loop: type query → see responses → pick winner → repeat.
  - Every judgement is persisted to a local CSV + the in-memory leaderboard.
  - After picking, the user can optionally add a comment.

Handles two battle modes:
  - PICK_BEST (1): Click on the best response card.
  - THUMBS    (2): Vote 👍 / 👎 on each response independently.
"""

from __future__ import annotations

import logging
import random
import string
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from vibediff.core.competitor import Competitor

logger = logging.getLogger(__name__)

# Anonymous labels used in blind evaluation
_LABELS = list(string.ascii_uppercase)  # A, B, C, D, ...


def launch_arena_ui(
    competitors: list["Competitor"],
    mode: int = 1,
    csv_path: str = "vibediff_results.csv",
    share: bool = False,
    description: str = "",
    **kwargs: Any,
) -> None:
    """
    Launch the full VibeDiff battleground as a persistent Gradio app.

    The UI runs in a continuous loop:
      1. User types a query.
      2. All competitors generate responses (anonymized).
      3. User picks the best / votes on each.
      4. Optional comment prompt.
      5. Result saved to CSV + leaderboard updated.
      6. Loop back to step 1.

    Args:
        competitors: List of Competitor objects to battle.
        mode:        1 = PICK_BEST,  2 = THUMBS.
        csv_path:    Path to the CSV file for persisting results.
        share:       If True, create a public Gradio share link.
        description: Custom description shown at the top of the UI.
    """
    try:
        import gradio as gr
    except ImportError as exc:
        raise ImportError(
            "Gradio is required for the UI. Install with: pip install gradio"
        ) from exc

    from vibediff.core.battle import BattleMode, BattleResult
    from vibediff.analytics.leaderboard import Leaderboard
    from vibediff.storage.csv_store import CSVStore

    battle_mode = BattleMode.from_value(mode)
    store = CSVStore(csv_path)
    leaderboard = Leaderboard()
    n = len(competitors)
    labels = _LABELS[:n]

    custom_css = _build_css(n)

    if battle_mode == BattleMode.PICK_BEST:
        _build_pick_best_app(
            competitors, labels, store, leaderboard, description, custom_css,
            share=share, **kwargs,
        )
    elif battle_mode == BattleMode.THUMBS:
        _build_thumbs_app(
            competitors, labels, store, leaderboard, description, custom_css,
            share=share, **kwargs,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE 1 — PICK BEST
# ═══════════════════════════════════════════════════════════════════════════════

def _build_pick_best_app(
    competitors, labels, store, leaderboard, description, custom_css,
    share=False, **kwargs,
):
    import gradio as gr
    from vibediff.core.battle import BattleMode, BattleResult

    n = len(competitors)

    with gr.Blocks(
        title="⚔️ VibeDiff Battleground",
        css=custom_css,
        theme=gr.themes.Base(
            primary_hue="violet",
            neutral_hue="slate",
            font=["Inter", "ui-sans-serif"],
        ),
    ) as demo:

        # ── Header ────────────────────────────────────────────────────────
        gr.HTML(_render_header_html(
            "Pick the Best Response",
            description or (
                "Type a query below. Multiple AI models will respond anonymously. "
                "Read all responses and **click the best one**. "
                "Your choices are recorded to build a fair leaderboard."
            ),
            n,
        ))

        # ── Hidden state ──────────────────────────────────────────────────
        # Stores the list of CompetitorResult dicts between generate & judge
        battle_state = gr.State(None)
        round_count = gr.State(0)

        # ── Step 1: User input ─────────────────────────────────────────────
        with gr.Group(elem_classes=["input-section"]):
            gr.Markdown("### 💬 Your Query")
            with gr.Row():
                query_input = gr.Textbox(
                    placeholder="Type your query here, e.g. 'Explain attention mechanisms in transformers'",
                    lines=2,
                    show_label=False,
                    elem_id="query_input",
                    scale=5,
                )
                generate_btn = gr.Button(
                    "⚡ Generate",
                    variant="primary",
                    elem_id="generate_btn",
                    scale=1,
                )

        # ── Step 2: Response cards (initially hidden) ──────────────────────
        response_section = gr.Group(visible=False, elem_id="response_section")

        with response_section:
            gr.Markdown("### 🎯 Click on the best response")
            status_bar = gr.Markdown("", elem_id="status_bar")

            response_boxes = []
            select_buttons = []

            with gr.Row(equal_height=True):
                for i in range(n):
                    with gr.Column(elem_classes=["response-card"], min_width=300):
                        gr.Markdown(
                            f"<div class='card-label'>Response {labels[i]}</div>",
                            elem_classes=["card-label-wrapper"],
                        )
                        tb = gr.Textbox(
                            label="",
                            lines=14,
                            interactive=False,
                            elem_id=f"resp_{labels[i]}",
                            elem_classes=["response-text"],
                        )
                        btn = gr.Button(
                            f"✅ Pick {labels[i]}",
                            variant="secondary",
                            elem_id=f"pick_{labels[i]}",
                            elem_classes=["pick-btn"],
                        )
                        response_boxes.append(tb)
                        select_buttons.append(btn)

        # ── Step 3: Comment dialog (initially hidden) ──────────────────────
        comment_section = gr.Group(visible=False, elem_id="comment_section")
        with comment_section:
            winner_label = gr.Markdown("", elem_id="winner_label")
            comment_input = gr.Textbox(
                label="💬 Why did you pick this one? (optional)",
                placeholder="Add a comment or just click Submit...",
                lines=2,
                elem_id="comment_input",
            )
            with gr.Row():
                submit_comment_btn = gr.Button(
                    "✅ Submit & Next Round",
                    variant="primary",
                    elem_id="submit_comment",
                    scale=2,
                )
                skip_comment_btn = gr.Button(
                    "⏩ Skip Comment & Next",
                    variant="secondary",
                    elem_id="skip_comment",
                    scale=1,
                )

        # ── Leaderboard section ────────────────────────────────────────────
        with gr.Accordion("📊 Live Leaderboard", open=False, elem_id="leaderboard_accordion"):
            leaderboard_display = gr.Dataframe(
                headers=["Rank", "Competitor", "ELO", "Wins", "Losses", "Win Rate", "Battles"],
                interactive=False,
                elem_id="leaderboard_table",
            )
            refresh_lb_btn = gr.Button("🔄 Refresh Leaderboard", size="sm")

        # ──────────────────────────────────────────────────────────────────
        # Event handlers
        # ──────────────────────────────────────────────────────────────────

        def on_generate(query, state, rd_count):
            if not query or not query.strip():
                updates = [gr.update()] * n  # don't change response boxes
                return (
                    state,
                    rd_count,
                    gr.update(),                  # response_section stays same
                    gr.update(value="⚠️ Please type a query first."),  # status
                    *updates,                     # response boxes
                )

            # Run all competitors
            results = []
            for comp in competitors:
                try:
                    result = comp.run({"query": query})
                    results.append(result)
                except Exception as e:
                    logger.exception("Competitor %s failed", comp.name)
                    # Create a dummy result for failed competitors
                    from vibediff.core.competitor import CompetitorResult
                    results.append(CompetitorResult(
                        competitor=comp,
                        rendered_prompt=comp.render_prompt({"query": query}),
                        response=f"[Error: {e}]",
                        raw_response=None,
                    ))

            # Shuffle to remove positional bias
            mapping = list(range(n))
            random.shuffle(mapping)
            shuffled = [results[mapping[i]] for i in range(n)]

            state = {
                "results": shuffled,
                "query": query.strip(),
                "mapping": mapping,
            }

            rd_count = (rd_count or 0) + 1

            updates = [gr.update(value=shuffled[i].response) for i in range(n)]

            return (
                state,
                rd_count,
                gr.update(visible=True),    # show response section
                gr.update(value=f"**Round {rd_count}** — Read all responses carefully, then pick the best one."),
                *updates,
            )

        def make_pick_handler(pick_index):
            def on_pick(state, comment_text):
                if not state or "results" not in state:
                    return (
                        state,
                        gr.update(),   # comment_section
                        gr.update(),   # winner_label
                    )
                state["winner_index"] = pick_index
                label = labels[pick_index]
                return (
                    state,
                    gr.update(visible=True),  # show comment section
                    gr.update(value=f"### 🏆 You picked **Response {label}**"),
                )
            return on_pick

        def on_submit_with_comment(state, comment, rd_count):
            return _finalize_pick_best(
                state, comment, rd_count, competitors, labels,
                store, leaderboard,
            )

        def on_skip_comment(state, rd_count):
            return _finalize_pick_best(
                state, "", rd_count, competitors, labels,
                store, leaderboard,
            )

        def refresh_leaderboard():
            return _get_leaderboard_df(leaderboard)

        # ── Wire events ───────────────────────────────────────────────────

        generate_outputs = [
            battle_state, round_count,
            response_section, status_bar,
            *response_boxes,
        ]
        generate_btn.click(
            on_generate,
            inputs=[query_input, battle_state, round_count],
            outputs=generate_outputs,
        )
        query_input.submit(
            on_generate,
            inputs=[query_input, battle_state, round_count],
            outputs=generate_outputs,
        )

        pick_outputs = [battle_state, comment_section, winner_label]
        for i, btn in enumerate(select_buttons):
            btn.click(
                make_pick_handler(i),
                inputs=[battle_state, comment_input],
                outputs=pick_outputs,
            )

        finalize_outputs = [
            battle_state,
            response_section,
            comment_section,
            status_bar,
            query_input,
            leaderboard_display,
        ]
        submit_comment_btn.click(
            on_submit_with_comment,
            inputs=[battle_state, comment_input, round_count],
            outputs=finalize_outputs,
        )
        skip_comment_btn.click(
            on_skip_comment,
            inputs=[battle_state, round_count],
            outputs=finalize_outputs,
        )

        refresh_lb_btn.click(
            refresh_leaderboard,
            outputs=[leaderboard_display],
        )

    demo.launch(share=share, **kwargs)


def _finalize_pick_best(state, comment, rd_count, competitors, labels, store, leaderboard):
    """Save the pick-best result to CSV + leaderboard and reset the UI for next round."""
    import gradio as gr
    from vibediff.core.battle import BattleMode, BattleResult

    if not state or "winner_index" not in state:
        return (
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
            gr.update(value=""),
            gr.update(),
        )

    results = state["results"]
    winner_idx = state["winner_index"]
    query = state.get("query", "")

    # Mark winner
    for i, r in enumerate(results):
        r.won = i == winner_idx

    winner_result = results[winner_idx]

    battle = BattleResult(
        mode=BattleMode.PICK_BEST,
        results=results,
        winner=winner_result,
        variables={"query": query},
    )

    # Persist
    store.save(battle, user_query=query, user_comment=comment)
    leaderboard.record(battle)

    lb_df = _get_leaderboard_df(leaderboard)

    return (
        None,                              # reset battle_state
        gr.update(visible=False),          # hide response_section
        gr.update(visible=False),          # hide comment_section
        gr.update(value=""),               # reset status
        gr.update(value=""),               # clear query input
        lb_df,                             # update leaderboard
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE 2 — THUMBS UP / DOWN
# ═══════════════════════════════════════════════════════════════════════════════

def _build_thumbs_app(
    competitors, labels, store, leaderboard, description, custom_css,
    share=False, **kwargs,
):
    import gradio as gr
    from vibediff.core.battle import BattleMode, BattleResult

    n = len(competitors)

    with gr.Blocks(
        title="⚔️ VibeDiff Battleground",
        css=custom_css,
        theme=gr.themes.Base(
            primary_hue="violet",
            neutral_hue="slate",
            font=["Inter", "ui-sans-serif"],
        ),
    ) as demo:

        gr.HTML(_render_header_html(
            "Rate Each Response",
            description or (
                "Type a query below. Multiple AI models will respond anonymously. "
                "Vote **👍 Good** or **👎 Not Good** on each response. "
                "Your votes build the leaderboard over time."
            ),
            n,
        ))

        battle_state = gr.State(None)
        round_count = gr.State(0)

        # ── Query input ───────────────────────────────────────────────────
        with gr.Group(elem_classes=["input-section"]):
            gr.Markdown("### 💬 Your Query")
            with gr.Row():
                query_input = gr.Textbox(
                    placeholder="Type your query here...",
                    lines=2,
                    show_label=False,
                    elem_id="query_input",
                    scale=5,
                )
                generate_btn = gr.Button(
                    "⚡ Generate", variant="primary", scale=1,
                )

        # ── Response cards ─────────────────────────────────────────────────
        response_section = gr.Group(visible=False)

        with response_section:
            gr.Markdown("### 🎯 Vote on each response")
            status_bar = gr.Markdown("")

            response_boxes = []
            vote_displays = []
            up_buttons = []
            down_buttons = []

            for i in range(n):
                with gr.Group(elem_classes=["response-card"]):
                    gr.Markdown(
                        f"<div class='card-label'>Response {labels[i]}</div>",
                        elem_classes=["card-label-wrapper"],
                    )
                    tb = gr.Textbox(
                        label="", lines=10, interactive=False,
                        elem_id=f"resp_{labels[i]}",
                        elem_classes=["response-text"],
                    )
                    with gr.Row():
                        up_btn = gr.Button(
                            f"👍 Good", variant="primary",
                            elem_id=f"thumb_up_{labels[i]}",
                            elem_classes=["thumb-btn"],
                        )
                        down_btn = gr.Button(
                            f"👎 Not Good", variant="stop",
                            elem_id=f"thumb_down_{labels[i]}",
                            elem_classes=["thumb-btn"],
                        )
                    vd = gr.Markdown("*No vote yet*", elem_id=f"vote_status_{labels[i]}")

                    response_boxes.append(tb)
                    vote_displays.append(vd)
                    up_buttons.append(up_btn)
                    down_buttons.append(down_btn)

        # ── Comment + Submit ───────────────────────────────────────────────
        submit_section = gr.Group(visible=False)
        with submit_section:
            comment_input = gr.Textbox(
                label="💬 Any overall comments? (optional)",
                placeholder="Add a comment or just click Submit...",
                lines=2,
            )
            with gr.Row():
                submit_btn = gr.Button(
                    "✅ Submit Votes & Next Round", variant="primary", scale=2,
                )
                skip_btn = gr.Button(
                    "⏩ Skip & Next", variant="secondary", scale=1,
                )

        # ── Leaderboard ───────────────────────────────────────────────────
        with gr.Accordion("📊 Live Leaderboard", open=False):
            leaderboard_display = gr.Dataframe(
                headers=["Rank", "Competitor", "ELO", "👍", "👎", "Thumb Score", "Battles"],
                interactive=False,
            )
            refresh_lb_btn = gr.Button("🔄 Refresh Leaderboard", size="sm")

        # ──────────────────────────────────────────────────────────────────
        # Event handlers
        # ──────────────────────────────────────────────────────────────────

        def on_generate(query, state, rd_count):
            if not query or not query.strip():
                updates = [gr.update()] * n
                vote_updates = [gr.update()] * n
                return (
                    state, rd_count,
                    gr.update(), gr.update(),  # response_section, submit_section
                    gr.update(value="⚠️ Please type a query first."),
                    *updates, *vote_updates,
                )

            results = []
            for comp in competitors:
                try:
                    results.append(comp.run({"query": query}))
                except Exception as e:
                    logger.exception("Competitor %s failed", comp.name)
                    from vibediff.core.competitor import CompetitorResult
                    results.append(CompetitorResult(
                        competitor=comp,
                        rendered_prompt=comp.render_prompt({"query": query}),
                        response=f"[Error: {e}]",
                        raw_response=None,
                    ))

            mapping = list(range(n))
            random.shuffle(mapping)
            shuffled = [results[mapping[i]] for i in range(n)]

            rd_count = (rd_count or 0) + 1

            state = {
                "results": shuffled,
                "query": query.strip(),
                "votes": {},
            }

            updates = [gr.update(value=shuffled[i].response) for i in range(n)]
            vote_updates = [gr.update(value="*No vote yet*") for _ in range(n)]

            return (
                state, rd_count,
                gr.update(visible=True),   # response_section
                gr.update(visible=True),   # submit_section
                gr.update(value=f"**Round {rd_count}** — Vote on each response."),
                *updates, *vote_updates,
            )

        def make_vote_handler(idx, val):
            def on_vote(state):
                if not state or "votes" not in state:
                    return state, gr.update()
                state["votes"][idx] = val
                label = "✅ Voted: **Good**" if val == 1 else "❌ Voted: **Not Good**"
                return state, gr.update(value=label)
            return on_vote

        def on_submit_votes(state, comment, rd_count):
            return _finalize_thumbs(
                state, comment, rd_count, competitors, labels,
                store, leaderboard,
            )

        def on_skip_votes(state, rd_count):
            return _finalize_thumbs(
                state, "", rd_count, competitors, labels,
                store, leaderboard,
            )

        def refresh_leaderboard_thumbs():
            return _get_leaderboard_df_thumbs(leaderboard)

        # ── Wire events ───────────────────────────────────────────────────

        gen_outputs = [
            battle_state, round_count,
            response_section, submit_section, status_bar,
            *response_boxes, *vote_displays,
        ]
        generate_btn.click(
            on_generate,
            inputs=[query_input, battle_state, round_count],
            outputs=gen_outputs,
        )
        query_input.submit(
            on_generate,
            inputs=[query_input, battle_state, round_count],
            outputs=gen_outputs,
        )

        for i in range(n):
            up_buttons[i].click(
                make_vote_handler(i, 1),
                inputs=[battle_state],
                outputs=[battle_state, vote_displays[i]],
            )
            down_buttons[i].click(
                make_vote_handler(i, -1),
                inputs=[battle_state],
                outputs=[battle_state, vote_displays[i]],
            )

        finalize_outputs = [
            battle_state,
            response_section, submit_section,
            status_bar, query_input,
            leaderboard_display,
        ]
        submit_btn.click(
            on_submit_votes,
            inputs=[battle_state, comment_input, round_count],
            outputs=finalize_outputs,
        )
        skip_btn.click(
            on_skip_votes,
            inputs=[battle_state, round_count],
            outputs=finalize_outputs,
        )

        refresh_lb_btn.click(
            refresh_leaderboard_thumbs,
            outputs=[leaderboard_display],
        )

    demo.launch(share=share, **kwargs)


def _finalize_thumbs(state, comment, rd_count, competitors, labels, store, leaderboard):
    """Save thumbs votes and reset."""
    import gradio as gr
    from vibediff.core.battle import BattleMode, BattleResult

    if not state or "results" not in state:
        return (
            None,
            gr.update(visible=False), gr.update(visible=False),
            gr.update(value=""), gr.update(value=""),
            gr.update(),
        )

    results = state["results"]
    votes = state.get("votes", {})
    query = state.get("query", "")

    # Apply votes
    for i, r in enumerate(results):
        r.vote = votes.get(i, 0)

    battle = BattleResult(
        mode=BattleMode.THUMBS,
        results=results,
        variables={"query": query},
    )

    store.save(battle, user_query=query, user_comment=comment)
    leaderboard.record(battle)

    lb_df = _get_leaderboard_df_thumbs(leaderboard)

    return (
        None,
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(value=""),
        gr.update(value=""),
        lb_df,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_header_html(title: str, description: str, n_competitors: int) -> str:
    return f"""
<div class="vd-header">
  <h1>⚔️ VibeDiff Battleground</h1>
  <p class="vd-subtitle">{title} &nbsp;·&nbsp; {n_competitors} Competitors</p>
  <p class="vd-description">{description}</p>
</div>
"""


def _get_leaderboard_df(leaderboard):
    rows = leaderboard.ranked()
    data = []
    for rank, s in enumerate(rows, 1):
        data.append([
            rank, s.name, round(s.elo, 1),
            s.wins, s.losses, f"{s.win_rate:.0%}", s.battles_played,
        ])
    return data


def _get_leaderboard_df_thumbs(leaderboard):
    rows = leaderboard.ranked()
    data = []
    for rank, s in enumerate(rows, 1):
        data.append([
            rank, s.name, round(s.elo, 1),
            s.thumbs_up, s.thumbs_down, f"{s.thumb_score:.0%}", s.battles_played,
        ])
    return data


def _build_css(n_competitors: int) -> str:
    return """
/* ── VibeDiff Battleground Styles ──────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --vd-bg: #0a0a10;
  --vd-surface: #14141f;
  --vd-surface-hover: #1c1c2e;
  --vd-border: #262640;
  --vd-border-active: #7c3aed;
  --vd-accent: #7c3aed;
  --vd-accent-glow: rgba(124, 58, 237, 0.3);
  --vd-green: #10b981;
  --vd-red: #ef4444;
  --vd-text: #e2e2f0;
  --vd-muted: #6b7280;
  --vd-radius: 14px;
}

body, .gradio-container {
  background: var(--vd-bg) !important;
  color: var(--vd-text) !important;
  font-family: 'Inter', system-ui, sans-serif !important;
}

/* ── Header ──────────────────────────────────────────────────────────── */

.vd-header {
  text-align: center;
  padding: 2.5rem 1rem 1.5rem;
}

.vd-header h1 {
  font-size: 2.4rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #c084fc 0%, #7c3aed 40%, #4f46e5 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 0.5rem;
}

.vd-subtitle {
  color: var(--vd-muted);
  font-size: 1rem;
  font-weight: 500;
  margin-bottom: 0.4rem;
}

.vd-description {
  color: var(--vd-muted);
  font-size: 0.85rem;
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.5;
}

/* ── Input section ───────────────────────────────────────────────────── */

.input-section {
  background: var(--vd-surface) !important;
  border: 1px solid var(--vd-border) !important;
  border-radius: var(--vd-radius) !important;
  padding: 1.2rem !important;
  margin-bottom: 1rem !important;
}

/* ── Response card ───────────────────────────────────────────────────── */

.response-card {
  background: var(--vd-surface) !important;
  border: 1px solid var(--vd-border) !important;
  border-radius: var(--vd-radius) !important;
  padding: 1.2rem !important;
  transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
}

.response-card:hover {
  border-color: var(--vd-border-active) !important;
  box-shadow: 0 0 20px var(--vd-accent-glow) !important;
}

.card-label {
  display: inline-block;
  background: linear-gradient(135deg, #7c3aed, #4f46e5);
  color: white;
  font-weight: 700;
  font-size: 0.85rem;
  padding: 0.3rem 0.9rem;
  border-radius: 20px;
  margin-bottom: 0.6rem;
  letter-spacing: 0.03em;
}

.response-text textarea {
  background: #0d0d15 !important;
  border: 1px solid var(--vd-border) !important;
  color: var(--vd-text) !important;
  border-radius: 10px !important;
  font-family: 'Inter', monospace !important;
  font-size: 0.88rem !important;
  line-height: 1.6 !important;
  padding: 1rem !important;
}

/* ── Pick button ─────────────────────────────────────────────────────── */

.pick-btn button {
  width: 100% !important;
  background: var(--vd-surface) !important;
  border: 2px solid var(--vd-border) !important;
  color: var(--vd-text) !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  padding: 0.7rem !important;
  transition: all 0.2s ease !important;
  cursor: pointer !important;
}

.pick-btn button:hover {
  background: var(--vd-accent) !important;
  border-color: var(--vd-accent) !important;
  color: white !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 16px var(--vd-accent-glow) !important;
}

/* ── Thumb buttons ───────────────────────────────────────────────────── */

.thumb-btn button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: transform 0.15s, box-shadow 0.2s !important;
}

.thumb-btn button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}

/* ── Primary buttons ─────────────────────────────────────────────────── */

button.primary {
  background: linear-gradient(135deg, #7c3aed, #4f46e5) !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: opacity 0.2s, transform 0.15s !important;
}

button.primary:hover {
  opacity: 0.92 !important;
  transform: translateY(-1px) !important;
}

/* ── Textareas ───────────────────────────────────────────────────────── */

textarea {
  background: #0d0d15 !important;
  border: 1px solid var(--vd-border) !important;
  color: var(--vd-text) !important;
  border-radius: 10px !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 0.9rem !important;
}

textarea:focus {
  border-color: var(--vd-accent) !important;
  box-shadow: 0 0 0 3px var(--vd-accent-glow) !important;
}

/* ── Leaderboard ─────────────────────────────────────────────────────── */

table {
  background: var(--vd-surface) !important;
  border-radius: 10px !important;
}

th {
  background: #1a1a30 !important;
  color: var(--vd-text) !important;
  font-weight: 600 !important;
}

td {
  color: var(--vd-text) !important;
  border-color: var(--vd-border) !important;
}

/* ── Misc ────────────────────────────────────────────────────────────── */

.gr-accordion {
  border: 1px solid var(--vd-border) !important;
  border-radius: var(--vd-radius) !important;
  background: var(--vd-surface) !important;
}

#status_bar {
  text-align: center;
  padding: 0.5rem 0;
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# OLD API COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

def launch_battle_ui(battle, share=False, **kwargs):
    """
    Legacy entrypoint — now redirects to the new arena UI.
    Called by Arena.battle() when launch_ui=True.
    """
    launch_arena_ui(
        competitors=[r.competitor for r in battle.results],
        mode=battle.mode.value,
        share=share,
        **kwargs,
    )
    return battle


def launch_ui():
    """Placeholder for standalone UI launch (used by vibediff.ui module)."""
    pass
