"use client";

import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";

import type { Evidence } from "@/lib/types";

const LABEL_COLORS: Record<string, string> = {
  Cylinder: "#27a987",
  CylinderBottom: "#4f8bea",
  PistonRod: "#8b6adf",
  Part: "#62746d",
  ProcessRun: "#e29a35",
  Process: "#d16e44",
  Equipment: "#de5d70",
  AnomalyClass: "#c54248",
  QualityMeasurement: "#3d9db2",
  QualityFailure: "#b6354e",
};

export function EvidenceGraph({
  evidence,
  className = "",
}: {
  evidence: Evidence;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || evidence.nodes.length === 0) return;

    const graph = cytoscape({
      container: containerRef.current,
      elements: [
        ...evidence.nodes.map((node) => {
          const label = node.label ?? node.labels?.[0] ?? "Node";
          const primary =
            node.properties.part_id ??
            node.properties.run_id ??
            node.properties.name ??
            node.properties.code ??
            node.properties.measurement_id ??
            node.id;
          return {
            data: {
              id: node.id,
              label,
              title: String(primary),
              color: LABEL_COLORS[label] ?? "#5c766d",
            },
          };
        }),
        ...evidence.relationships.map((relationship, index) => ({
          data: {
            id:
              relationship.id ??
              `${relationship.source}-${relationship.type}-${relationship.target}-${index}`,
            source: relationship.source,
            target: relationship.target,
            label: relationship.type,
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            "border-color": "#ffffff",
            "border-width": 2,
            color: "#dcece6",
            "font-family": "Geist, sans-serif",
            "font-size": 8,
            label: "data(title)",
            "text-background-color": "#10211b",
            "text-background-opacity": 0.82,
            "text-background-padding": "4px",
            "text-background-shape": "roundrectangle",
            "text-margin-y": 17,
            width: 29,
            height: 29,
          },
        },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "line-color": "#6d8d82",
            "target-arrow-color": "#6d8d82",
            "target-arrow-shape": "triangle",
            width: 1.2,
            label: "data(label)",
            color: "#8da69d",
            "font-size": 6,
            "text-background-color": "#10211b",
            "text-background-opacity": 0.75,
            "text-background-padding": "2px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#f4b953",
            "border-width": 4,
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 34,
        nodeRepulsion: () => 7000,
      },
      minZoom: 0.35,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
    });

    return () => graph.destroy();
  }, [evidence]);

  if (evidence.nodes.length === 0) {
    return (
      <div className={`graph-empty ${className}`}>
        집계 질의이거나 반환된 경로 ID가 없어 그래프를 임의 생성하지
        않습니다.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`evidence-graph ${className}`}
      aria-label={`근거 그래프: 노드 ${evidence.node_count}개, 관계 ${evidence.relationship_count}개`}
    />
  );
}
