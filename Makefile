
.PHONY: test

test: Thing.class
	mypy jvm.py
	python jvm.py

%.class: %.java
	javac $^
