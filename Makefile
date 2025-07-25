.PHONY: test coverage lint clean

test:
	./scripts/run_tests.sh all

coverage:
	./scripts/run_tests.sh coverage

lint:
	./scripts/run_tests.sh lint

clean:
	./scripts/run_tests.sh clean
