import type { Route } from "@playwright/test";

export function interpretationFixture(
  question: string,
  displayInterpretation = `Interpreté que desea investigar «${question}».`,
  warnings: string[] = [],
) {
  return {
    phase: "interpretation",
    status: "awaiting_confirmation",
    interpretation_id: `e2e-${encodeURIComponent(question)}`,
    conversation_id: "e2e-confirmation-conversation",
    original_query: question,
    display_interpretation: displayInterpretation,
    query_understanding: {
      original_query: question,
      intent: "unknown",
      operation: "investigate_query",
      instruction_span: null,
      subject_span: null,
      subject: {
        raw: question,
        canonical: question,
        normalized: question.toLocaleLowerCase(),
        subject_type: "query",
      },
      typo_resolution: null,
      reason_codes: [],
      confidence: 0.5,
      ai_used: false,
      fallback_used: true,
    },
    actions: ["analyze", "modify"],
    warnings,
    expires_at: null,
    execution: { retrieval_executed: false },
  };
}

export async function fulfillConfirmationPhases(
  route: Route,
  analysis: Record<string, unknown>,
  displayInterpretation?: string,
) {
  const request = route.request().postDataJSON() as {
    phase?: string;
    question?: string;
  };
  if (request.phase === "interpret") {
    await route.fulfill({
      json: interpretationFixture(
        request.question ?? "consulta",
        displayInterpretation,
        Array.isArray(analysis.warnings)
          ? analysis.warnings.filter((warning): warning is string => typeof warning === "string")
          : [],
      ),
    });
    return;
  }
  await route.fulfill({ json: analysis });
}
