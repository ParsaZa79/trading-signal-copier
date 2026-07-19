import { describe, expect, it } from "vitest";
import { passwordResetEmail } from "./email";

describe("password reset email", () => {
  it("renders a branded, accessible HTML email with a useful plain-text fallback", async () => {
    const resetUrl =
      "https://dashboard.example.test/sign-in/reset-password?token=single-use-token&source=email";
    const message = await passwordResetEmail("user@example.test", resetUrl);

    expect(message.subject).toBe("Reset your Signal Copier password");
    expect(message.to).toBe("user@example.test");
    expect(message.html).toContain("Signal Copier");
    expect(message.html).toContain("Reset your password");
    expect(message.html).toContain(
      "Use the secure link below to choose a new password.",
    );
    expect(message.html).toContain("Reset password");
    expect(message.html).toContain("Expires in one hour");
    expect(message.html).toContain("Works once");
    expect(message.html).toContain("your password won&#x27;t change");
    expect(message.html).toContain(
      "https://dashboard.kiaparsaprintingmoneymachine.cloud/email-assets/signal-wave-masthead.png",
    );
    expect(message.html).toContain(
      "https://dashboard.kiaparsaprintingmoneymachine.cloud/email-assets/shield-check.png",
    );
    expect(message.html).toContain(
      "https://dashboard.kiaparsaprintingmoneymachine.cloud/email-assets/key-round.png",
    );
    expect(message.html).toContain("rgb(130,156,255)");
    expect(message.html).toContain("single-use-token&amp;source=email");
    expect(message.html.length).toBeLessThan(102_400);

    expect(message.text).toContain("Signal Copier");
    expect(message.text).toContain("RESET YOUR PASSWORD");
    expect(message.text).toContain(resetUrl);
    expect(message.text).toContain("Expires in one hour · Works once");
    expect(message.text).toContain("your password won't change");
  });
});
