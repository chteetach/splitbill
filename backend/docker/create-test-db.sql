-- Runs once when the PostgreSQL volume is first created. The test suite drops and
-- recreates every table in this database, so it is kept separate from the app database.
CREATE DATABASE splitbill_test;
