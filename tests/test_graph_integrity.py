import os
import socket
import unittest

from neo4j import GraphDatabase

from backend.app.etl.cli import password_from_keychain
from backend.app.etl.load import graph_counts
from backend.app.etl.validate import EXPECTED_COUNTS


def neo4j_credentials() -> tuple[str, str] | None:
    try:
        with socket.create_connection(("localhost", 7687), timeout=0.5):
            pass
    except OSError:
        return None
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or password_from_keychain(username)
    return (username, password) if password else None


@unittest.skipUnless(
    neo4j_credentials(),
    "local Neo4j credentials are required for graph integrity tests",
)
class GraphIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = os.getenv("NEO4J_DATABASE", "neo4j")
        username, password = neo4j_credentials()
        cls.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            auth=(username, password),
        )
        cls.driver.verify_connectivity()

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def query_one(self, cypher):
        records, _, _ = self.driver.execute_query(
            cypher,
            database_=self.database,
            routing_="r",
        )
        return records[0].data()

    def test_node_and_relationship_counts_match_validated_payload(self):
        self.assertEqual(
            graph_counts(self.driver, self.database),
            EXPECTED_COUNTS,
        )

    def test_unique_key_constraints_are_online(self):
        records, _, _ = self.driver.execute_query(
            """
            SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties
            RETURN name, labelsOrTypes, properties
            ORDER BY name
            """,
            database_=self.database,
            routing_="r",
        )
        self.assertEqual(
            {record["name"] for record in records},
            {
                "anomaly_class_code_unique",
                "equipment_id_unique",
                "measurement_id_unique",
                "part_id_unique",
                "process_name_unique",
                "process_run_id_unique",
            },
        )

    def test_process_runs_have_one_complete_provenance_path(self):
        result = self.query_one(
            """
            MATCH (run:ProcessRun)
            OPTIONAL MATCH (:Part)-[underwent:UNDERWENT]->(run)
            OPTIONAL MATCH (run)-[instance:INSTANCE_OF]->(:Process)
            OPTIONAL MATCH (run)-[on:RUN_ON]->(:Equipment)
            OPTIONAL MATCH (run)-[classified:CLASSIFIED_AS]->
                           (:AnomalyClass)
            WITH run,
                 count(DISTINCT underwent) AS underwent_count,
                 count(DISTINCT instance) AS instance_count,
                 count(DISTINCT on) AS equipment_count,
                 count(DISTINCT classified) AS anomaly_count
            WHERE underwent_count <> 1 OR instance_count <> 1
               OR equipment_count <> 1 OR anomaly_count <> 1
            RETURN count(run) AS invalid_count
            """
        )
        self.assertEqual(result["invalid_count"], 0)

    def test_measurements_have_one_part_and_process(self):
        result = self.query_one(
            """
            MATCH (measurement:QualityMeasurement)
            OPTIONAL MATCH (:Part)-[has:HAS_MEASUREMENT]->(measurement)
            OPTIONAL MATCH (measurement)-[for_process:FOR_PROCESS]->
                           (:Process)
            WITH measurement,
                 count(DISTINCT has) AS part_count,
                 count(DISTINCT for_process) AS process_count
            WHERE part_count <> 1 OR process_count <> 1
            RETURN count(measurement) AS invalid_count
            """
        )
        self.assertEqual(result["invalid_count"], 0)

    def test_genealogy_gap_is_known_and_bounded(self):
        result = self.query_one(
            """
            MATCH (cylinder:Cylinder)
            OPTIONAL MATCH (cylinder)-[:ASSEMBLED_FROM]->(part:Part)
            WITH cylinder, count(part) AS component_count
            RETURN count(cylinder) AS total,
                   sum(CASE WHEN component_count = 2 THEN 1 ELSE 0 END)
                     AS complete,
                   sum(CASE WHEN component_count <> 2 THEN 1 ELSE 0 END)
                     AS incomplete
            """
        )
        self.assertEqual(
            result,
            {"total": 802, "complete": 767, "incomplete": 35},
        )


if __name__ == "__main__":
    unittest.main()
