"use client";

import { LoaderCircle, Network, Search } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { EvidenceGraph } from "@/components/evidence-graph";
import {
  getGraphSchema,
  getSubgraph,
  searchGraphNodes,
} from "@/lib/api";
import type {
  EvidenceNode,
  GraphSchema,
  NodeSearchResponse,
  SubgraphResponse,
} from "@/lib/types";
import { useProject } from "@/components/project-context";

function nodeTitle(node: EvidenceNode, identityProperty: string) {
  const value = node.properties[identityProperty];
  const secondary =
    node.properties.display_name ??
    node.properties.name ??
    node.properties.part_type ??
    node.properties.feature;
  return [String(value ?? node.id), secondary ? String(secondary) : ""]
    .filter(Boolean)
    .join(" · ");
}

export function GraphExplorer() {
  const { activeProject } = useProject();
  const projectId = activeProject?.project_id ?? "cip-dmd";
  const [schema, setSchema] = useState<GraphSchema | null>(null);
  const [label, setLabel] = useState("Cylinder");
  const [identity, setIdentity] = useState("300002");
  const [depth, setDepth] = useState(2);
  const [result, setResult] = useState<SubgraphResponse | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResult, setSearchResult] =
    useState<NodeSearchResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);

  useEffect(() => {
    getGraphSchema(projectId).then((nextSchema) => {
      setSchema(nextSchema);
      const first = nextSchema.node_identities[0];
      if (first) setLabel(first.label);
    }).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "스키마 조회 실패");
    });
  }, [projectId]);

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!searchTerm.trim()) return;
    setSearchLoading(true);
    setError("");
    try {
      setSearchResult(
        await searchGraphNodes(label, searchTerm.trim(), 12, projectId),
      );
    } catch (reason) {
      setSearchResult(null);
      setError(reason instanceof Error ? reason.message : "노드 검색 실패");
    } finally {
      setSearchLoading(false);
    }
  };

  const selectNode = async (
    node: EvidenceNode,
    identityProperty: string,
  ) => {
    const selectedIdentity = String(node.properties[identityProperty] ?? "");
    if (!selectedIdentity) return;
    setIdentity(selectedIdentity);
    setLoading(true);
    setError("");
    try {
      setResult(await getSubgraph(label, selectedIdentity, depth, projectId));
    } catch (reason) {
      setResult(null);
      setError(
        reason instanceof Error ? reason.message : "부분 그래프 조회 실패",
      );
    } finally {
      setLoading(false);
    }
  };

  const explore = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!identity.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResult(await getSubgraph(label, identity.trim(), depth, projectId));
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
      <form className="graph-discovery" onSubmit={search}>
        <div>
          <strong>먼저 노드를 검색하세요.</strong>
          <span>ID를 몰라도 이름·유형·측정 항목의 일부로 찾을 수 있습니다.</span>
        </div>
        <input
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="예: pressure, anomaly, 3000"
          aria-label="노드 검색어"
        />
        <button
          className="secondary-button"
          type="submit"
          disabled={searchLoading}
        >
          {searchLoading ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Search size={16} />
          )}
          노드 검색
        </button>
      </form>

      {searchResult && (
        <div className="graph-search-results">
          <div className="graph-search-results-head">
            <strong>{searchResult.count}개 검색 결과</strong>
            <span>
              {searchResult.label} · {searchResult.identity_property}
            </span>
          </div>
          {searchResult.nodes.length ? (
            <div className="graph-search-result-list">
              {searchResult.nodes.map((node) => (
                <button
                  type="button"
                  key={node.id}
                  onClick={() =>
                    selectNode(node, searchResult.identity_property)
                  }
                >
                  <span>{node.labels?.join(" / ") ?? label}</span>
                  <strong>
                    {nodeTitle(node, searchResult.identity_property)}
                  </strong>
                  <small>선택하여 {depth}-hop 탐색</small>
                </button>
              ))}
            </div>
          ) : (
            <p>일치하는 노드가 없습니다. 다른 검색어를 입력해보세요.</p>
          )}
        </div>
      )}

      <form className="graph-search" onSubmit={explore}>
        <label>
          Node label
          <select
            value={label}
            onChange={(event) => {
              setLabel(event.target.value);
              setSearchResult(null);
            }}
          >
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
