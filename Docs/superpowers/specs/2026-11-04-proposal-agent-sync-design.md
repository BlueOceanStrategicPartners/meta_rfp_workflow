# Proposal ↔ assistant live sync

**Status:** Implemented (2026-11-04)

## Summary

Client full-screen proposal iframe emits structured events via `postMessage`. `ClientWorkspace` forwards them over `ws/rfp/{session}/` as `proposal_interaction_submit`. Mutations map to `validate_card_mutation`, reprice, re-render proposal HTML, and append session events the voice assistant reads in `build_agent_context_block()`.

## Designer contract

- `proposal_client_bridge.js` + declarative `data-proposal-action` / `data-proposal-mutation`
- Check template auto-adds script tag via `ensure_client_bridge_script_tag`
- `{{cta_accept_button}}` includes `data-proposal-action="accept"`

## Client

- `ProposalTemplateRenderer` listens for `rfp-proposal-event` and `venue-map-select`
- `useBidirectionalAgentUI.submitProposalInteraction`

## Backend

- `proposal_interaction.handle_proposal_interaction`
- `RFPSessionConsumer` message type `proposal_interaction_submit`
- Compile injects bridge via `inject_proposal_client_bridge`
