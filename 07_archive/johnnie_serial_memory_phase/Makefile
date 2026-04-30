# Makefile for memory-bound and serial phase testing

.PHONY: all setup memory serial clean help

all: setup memory serial

setup:
	@echo "Setting up test environment..."
	chmod +x *.sh *.py
	@./setup_test_environment.sh

memory:
	@echo "Starting memory-bound phase testing..."
	@./memory_bound_phase_test.sh

serial:
	@echo "Starting serial computation phase testing..."
	@./serial_computation_phase_test.sh

clean:
	@echo "Cleaning test results..."
	rm -f *.log *.json *.png
	rm -rf results/

help:
	@echo "Available targets:"
	@echo "  setup   - Setup test environment and dependencies"
	@echo "  memory  - Run memory-bound phase testing"
	@echo "  serial  - Run serial computation phase testing"
	@echo "  all     - Run setup, then both test suites"
	@echo "  clean   - Remove all generated files"
	@echo "  help    - Show this help message"