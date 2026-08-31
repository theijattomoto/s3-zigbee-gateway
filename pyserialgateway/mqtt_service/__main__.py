"""Standalone runner for validating the shared S3 Zigbee MQTT transport."""

import argparse
import logging
import signal
import sys
import time

from .config import MQTTConfig
from .events import GatewayEvent
from .service import MQTTService


def build_parser():
    parser = argparse.ArgumentParser(
        description="Start the shared S3 Zigbee MQTT service without the gateway runtime."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for broker connection before failing (default: 15).",
    )
    parser.add_argument(
        "--publish-test",
        action="store_true",
        help="Publish one non-retained gateway smoke-test event after connecting.",
    )
    parser.add_argument(
        "--stay-alive",
        action="store_true",
        help="Remain connected until Ctrl-C so subscriptions/LWT can be observed.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = MQTTConfig.from_env()
    if not config.enabled:
        print("ERROR: MQTT_ENABLED must be true for the standalone smoke test.", file=sys.stderr)
        return 2

    service = MQTTService(config)
    service.set_command_handler(
        lambda command: logging.getLogger("S3MQTT.SMOKE").info(
            "Received command: %s", command
        )
    )

    stopping = False

    def _stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        service.start()
        if not service.connected.wait(timeout=args.timeout):
            print(
                f"ERROR: MQTT broker connection was not established within {args.timeout:.1f}s.",
                file=sys.stderr,
            )
            return 1

        print(
            f"MQTT CONNECTED gateway_id={config.gateway_id} "
            f"broker={config.broker}:{config.port} "
            f"status_topic={service.topics.status()}"
        )

        if args.publish_test:
            service.publish_event(
                GatewayEvent(
                    event_type="smoke_test",
                    gateway_id=config.gateway_id,
                    node_id="gateway",
                    packet_type="standalone",
                    payload={"status": "ok", "source": "mqtt_service_smoke_test"},
                )
            )
            service.publish_queue.join()
            print(f"MQTT TEST EVENT QUEUED topic={service.topics.event('gateway')}")

        if args.stay_alive:
            print("MQTT service is running. Press Ctrl-C to stop cleanly.")
            while not stopping:
                time.sleep(0.5)

        return 0
    finally:
        service.stop()


if __name__ == "__main__":
    raise SystemExit(main())
