"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { queryFactoryGraph, submitExpertFeedback } from "@/lib/api";
import { readHistory, saveConversation } from "@/lib/history";
import type {
  FeedbackDecision,
  QueryResponse,
  StoredConversation,
} from "@/lib/types";
import type { EvidenceTab } from "@/components/query/query-config";
import { QUERY_PROGRESS } from "@/components/query/query-config";

export function useQuerySession(
  projectId: string,
  conversationId: string | null,
) {
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [history, setHistory] = useState<StoredConversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<EvidenceTab>("table");
  const [copied, setCopied] = useState(false);
  const [reviewer, setReviewer] = useState("domain-expert");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewDecision, setReviewDecision] =
    useState<FeedbackDecision | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const requestInFlightRef = useRef(false);

  const resetReview = useCallback(() => {
    setReviewDecision(null);
    setReviewNote("");
    setReviewError("");
  }, []);

  const loadConversation = useCallback((item: StoredConversation) => {
    setQuestion(item.question);
    setSubmittedQuestion(item.question);
    setResponse(item.response);
    setActiveTab("table");
    resetReview();
  }, [resetReview]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const stored = readHistory(projectId);
      setHistory(stored);
      setQuestion("");
      setSubmittedQuestion("");
      setResponse(null);
      setError("");
      resetReview();
      const selected = stored.find((item) => item.id === conversationId);
      if (selected) loadConversation(selected);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [conversationId, loadConversation, projectId, resetReview]);

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(
      () =>
        setProgressIndex((index) =>
          Math.min(index + 1, QUERY_PROGRESS.length - 1),
        ),
      650,
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  async function runQuestion(input: string) {
    const normalized = input.trim();
    if (!normalized || requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    setLoading(true);
    setQuestion("");
    setProgressIndex(0);
    setError("");
    setResponse(null);
    resetReview();
    setSubmittedQuestion(normalized);
    try {
      const result = await queryFactoryGraph(normalized, projectId);
      setResponse(result);
      setActiveTab("table");
      const now = new Date().toISOString();
      const item: StoredConversation = {
        id: crypto.randomUUID(),
        title:
          normalized.length > 38
            ? `${normalized.slice(0, 37)}…`
            : normalized,
        createdAt: now,
        updatedAt: now,
        question: normalized,
        response: result,
        projectId,
      };
      setHistory(saveConversation(item, projectId));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "질의를 처리하지 못했습니다.",
      );
    } finally {
      requestInFlightRef.current = false;
      setLoading(false);
    }
  }

  function prepareFollowUp(value = submittedQuestion) {
    setQuestion(value);
    setError("");
  }

  async function copyCypher() {
    if (!response?.cypher) return;
    await navigator.clipboard.writeText(response.cypher);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  async function submitReview(decision: FeedbackDecision) {
    if (!response || reviewLoading) return;
    setReviewLoading(true);
    setReviewError("");
    try {
      await submitExpertFeedback({
        project_id: projectId,
        question: response.question,
        cypher: response.cypher,
        query_status: response.status,
        provider: response.provider,
        row_count: response.row_count,
        decision,
        reviewer: reviewer.trim() || "domain-expert",
        note: reviewNote.trim(),
      });
      setReviewDecision(decision);
    } catch (reason) {
      setReviewError(
        reason instanceof Error ? reason.message : "검증 기록 저장 실패",
      );
    } finally {
      setReviewLoading(false);
    }
  }

  return {
    question,
    setQuestion,
    submittedQuestion,
    response,
    history,
    loading,
    progressIndex,
    error,
    activeTab,
    setActiveTab,
    copied,
    reviewer,
    setReviewer,
    reviewNote,
    setReviewNote,
    reviewDecision,
    reviewLoading,
    reviewError,
    runQuestion,
    prepareFollowUp,
    loadConversation,
    copyCypher,
    submitReview,
  };
}

export type QuerySession = ReturnType<typeof useQuerySession>;
