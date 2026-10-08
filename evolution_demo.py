"""Demonstrate old and new chat clients communicating through generated mappings."""

import importlib.util
from pathlib import Path
import tempfile

from veriflow.evolution import (compile_evolution, format_compatibility,
                                generate_adapters, verify_round_trip)
from veriflow.evolution_parser import parse_evolution


def main() -> None:
    root = Path(__file__).parent
    source = (root / "examples" / "chat_evolution.vfl").read_text(encoding="utf-8")
    plan = compile_evolution(parse_evolution(source))
    old_message = {"sender": "Old client", "message": "Hello from version 1"}
    new_reply = {"user": "New client", "content": "Reply from version 2",
                 "timestamp": "2026-09-17T10:30:00+05:30"}
    with tempfile.TemporaryDirectory(prefix="veriflow-adapters-") as folder:
        generated = generate_adapters(plan, Path(folder))
        spec = importlib.util.spec_from_file_location("generated_compatibility", generated[2])
        adapter = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(adapter)
        translated_for_new = adapter.translate(old_message, "ChatV2")
        translated_for_old = adapter.translate(new_reply, "ChatV1")
    round_trip = verify_round_trip(plan, old_message)

    print("VERIFLOW SCHEMA-EVOLUTION CHAT DEMO")
    print("=" * 72)
    print("\nGENERATED PROGRAMS\n forward_adapter.py\n reverse_adapter.py\n compatibility_adapter.py")
    print("\nOLD CLIENT SENDS\n", old_message)
    print("\nADAPTER TRANSLATES V1 -> V2\n", translated_for_new)
    print("\nNEW CLIENT REPLIES\n", new_reply)
    print("\nADAPTER TRANSLATES V2 -> V1\n", translated_for_old)
    print("\nROUND-TRIP PRESERVES OLD MESSAGE:", "YES" if round_trip.preserved else "NO")
    print("\n" + format_compatibility(plan))


if __name__ == "__main__":
    main()
