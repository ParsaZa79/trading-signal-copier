import nodemailer from "nodemailer";

export interface SmtpSettings {
  from: string;
  host: string;
  password: string;
  port: number;
  secure: boolean;
  user: string;
}

export interface AuthEmailMessage {
  html: string;
  subject: string;
  text: string;
  to: string;
}

export type AuthEmailSender = (message: AuthEmailMessage) => Promise<void>;

export function createSmtpEmailSender(settings: SmtpSettings): AuthEmailSender {
  let transporter: ReturnType<typeof nodemailer.createTransport> | undefined;

  return async (message) => {
    transporter ??= nodemailer.createTransport({
      host: settings.host,
      port: settings.port,
      secure: settings.secure,
      requireTLS: !settings.secure,
      auth: {
        user: settings.user,
        pass: settings.password,
      },
      logger: false,
      debug: false,
      disableFileAccess: true,
      disableUrlAccess: true,
      connectionTimeout: 10_000,
      greetingTimeout: 10_000,
      socketTimeout: 20_000,
    });

    await transporter.sendMail({
      from: settings.from,
      to: message.to,
      subject: message.subject,
      text: message.text,
      html: message.html,
    });
  };
}

export function verificationEmail(to: string, url: string): AuthEmailMessage {
  const safeUrl = escapeHtml(url);
  return {
    to,
    subject: "Verify your email address",
    text: `Verify your email address: ${url}`,
    html: `<p>Verify your email address:</p><p><a href="${safeUrl}">Verify email</a></p>`,
  };
}

export function passwordResetEmail(to: string, url: string): AuthEmailMessage {
  const safeUrl = escapeHtml(url);
  return {
    to,
    subject: "Reset your password",
    text: `Reset your password: ${url}`,
    html: `<p>Reset your password:</p><p><a href="${safeUrl}">Reset password</a></p>`,
  };
}

function escapeHtml(value: string) {
  return value.replace(
    /[&<>'"]/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
      })[character]!,
  );
}
