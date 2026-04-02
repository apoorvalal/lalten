#!/bin/bash

set -e

project=jot

printHelp () {
	echo "Usage: control.sh <command>"
	echo "Available commands:"
	echo
	echo "   start        Builds docker image and starts the service."
	echo "   startdev     Builds docker image and starts in dev mode (port 3210)."
	echo "   stop         Stops the service."
	echo "   logs         Tail -f service logs."
	echo "   shell        Opens a shell into the container."
}

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
pushd $dir > /dev/null

mkdir -p data/notes

case "$1" in
start)
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.prod.yml build
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.prod.yml up -d
	;;
startdev)
	docker compose -p $project -f docker-compose.base.yml down -t 1
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.dev.yml build
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.dev.yml up
	;;
stop)
	docker compose -p $project -f docker-compose.base.yml down -t 1
	;;
shell)
	docker exec -it ${project}_app bash
	;;
logs)
	docker compose -p $project -f docker-compose.base.yml logs -f
	;;
*)
	echo "Invalid command $1"
	printHelp
	;;
esac

popd > /dev/null
