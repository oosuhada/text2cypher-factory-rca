"use client";

import { LoaderCircle, Network, Search } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { EvidenceGraph } from "@/components/evidence-graph";
import { getGraphSchema, getSubgraph } from "@/lib/api";
import type {
  GraphSchema,
  SubgraphResponse,
} from "@/lib/types";

export function GraphExplorer() {
  const [schema, setSchema] = useState<GraphSchema | null>(null);
  const [label, setLabel] = useState("Cylinder");
  const [identity, setIdentity] = useState("300002");
  const [depth, setDepth] = useState(2);
  const [result, setResult] = useState<SubgraphResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getGraphSchema().then(setSchema).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "스키마 조회 실패");
    });
  }, []);

  const explore = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!identity.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResult(await getSubgraph(label, identity.trim(), depth));
    } catch (reason) {
      setResult(null);
      setError(
        reason instanceof Error ? reason.message : "부분 그래프 조회 실패",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="graph-explorer card">
      <form className="graph-search" onSubmit={explore}>
        <label>
          Node label
          <select value={label} onChange={(event) => setLabel(event.target.value)}>
            {(schema?.node_identities ?? []).map((node) => (
              <option key={node.label} value={node.label}>
                {node.label} · {node.identity_property}
              </option>
            ))}
          </select>
        </label>
        <label>
          Identity
          <input
            value={identity}
            onChange={(event) => setIdentity(event.target.value)}
            placeholder="300002"
          />
        </label>
        <label>
          Depth
          <select
            value={depth}
            onChange={(event) => setDepth(Number(event.target.value))}
          >
            <option value={1}>1-hop</option>
            <option value={2}>2-hop</option>
            <option value={3}>3-hop</option>
          </select>
        </label>
        <button className="primary-button" type="submit" disabled={loading}>
          {loading ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Search size={16} />
          )}
          탐색
        </button>
      </form>

      {error && <div className="inline-error">{error}</div>}

      {!result && !loading && (
        <div className="graph-explorer-empty">
          <Network size={35} />
          <h2>식별자에서 관계를 펼쳐보세요.</h2>
          <p>
            허용된 노드 라벨과 최대 3-hop 범위 안에서 읽기 전용으로
            조회합니다.
          </p>
        </div>
      )}

      {result && (
        <div className="graph-explorer-result">
          <div className="graph-result-stats">
            <span>
              <strong>{result.node_count}</strong> nodes
            </span>
            <span>
              <strong>{result.relationship_count}</strong> relationships
            </span>
            <span>
              <strong>{result.depth}</strong> hop depth
            </span>
          </div>
          <EvidenceGraph
            evidence={{
              nodes: result.nodes,
              relationships: result.relationships,
              node_count: result.node_count,
              relationship_count: result.relationship_count,
              truncated: result.truncated,
            }}
            className="explorer-canvas"
          />
        </div>
      )}
    </div>
  );
}
