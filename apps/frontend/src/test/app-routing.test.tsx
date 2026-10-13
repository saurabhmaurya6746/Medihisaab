import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "@/App";

describe("App routing and public pages", () => {
  it("matches and renders the homepage for /", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/Your daily hisaab/i)).toBeInTheDocument();
  });

  it("renders /product page with pharmacy billing and inventory content", () => {
    render(
      <MemoryRouter initialEntries={["/product"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: /Pharmacy billing/i })).toBeInTheDocument();
  });

  it("renders /how-it-works setup guide", () => {
    render(
      <MemoryRouter initialEntries={["/how-it-works"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/From sign-up to your first bill/i)).toBeInTheDocument();
  });

  it("renders /plans page with pricing and trial explanations", () => {
    render(
      <MemoryRouter initialEntries={["/plans"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/Try it in your store before you decide/i)).toBeInTheDocument();
  });

  it("renders /support page", () => {
    render(
      <MemoryRouter initialEntries={["/support"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: /How can we help\?/i })).toBeInTheDocument();
  });

  it("renders /about page", () => {
    render(
      <MemoryRouter initialEntries={["/about"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/Software for the work behind the counter/i)).toBeInTheDocument();
  });

  it("renders /privacy page", () => {
    render(
      <MemoryRouter initialEntries={["/privacy"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: /Privacy information/i })).toBeInTheDocument();
  });

  it("renders /faq page", () => {
    render(
      <MemoryRouter initialEntries={["/faq"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/Frequently asked questions/i)).toBeInTheDocument();
  });

  it("renders 404 page for unknown routes", () => {
    render(
      <MemoryRouter initialEntries={["/non-existent-page"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText(/Page not found/i)).toBeInTheDocument();
  });
});
