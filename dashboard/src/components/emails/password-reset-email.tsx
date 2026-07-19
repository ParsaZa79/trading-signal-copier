import {
  Body,
  Button,
  Container,
  Head,
  Heading,
  Hr,
  Html,
  Img,
  Link,
  Preview,
  Column,
  Row,
  Section,
  Tailwind,
  Text,
} from "react-email";
import { emailTailwindConfig } from "./email-theme";

interface PasswordResetEmailProps {
  assetBaseUrl?: string;
  resetUrl: string;
}

const PRODUCTION_ASSET_BASE_URL =
  "https://dashboard.kiaparsaprintingmoneymachine.cloud";

export function PasswordResetEmail({
  assetBaseUrl = PRODUCTION_ASSET_BASE_URL,
  resetUrl,
}: PasswordResetEmailProps) {
  const normalizedAssetBaseUrl = assetBaseUrl.replace(/\/$/, "");
  const assetUrl = (name: string) =>
    `${normalizedAssetBaseUrl}/email-assets/${name}`;

  return (
    <Html lang="en" dir="ltr">
      <Tailwind config={emailTailwindConfig}>
        <Head>
          <title>Reset your Signal Copier password</title>
        </Head>
        <Body className="m-0 bg-canvas px-[16px] py-[40px] font-sans">
          <Preview>
            Reset your Signal Copier password. This link expires in one hour.
          </Preview>

          <Container className="mx-auto max-w-[600px] overflow-hidden rounded-[14px] border border-solid border-line border-l-[4px] border-l-accent bg-surface">
            <Img
              src={assetUrl("signal-wave-masthead.png")}
              alt="Signal Copier"
              width="596"
              height="175"
              className="block h-auto w-full border-none"
            />

            <Section className="px-[36px] pb-[36px] pt-[38px]">
              <Section className="mx-auto w-[72px] rounded-full border border-solid border-line bg-surfaceRaised px-[10px] py-[10px]">
                <Img
                  src={assetUrl("shield-check.png")}
                  alt=""
                  width="52"
                  height="52"
                  className="mx-auto block"
                />
              </Section>

              <Heading className="mb-0 mt-[22px] text-center text-[34px] font-semibold leading-[40px] tracking-[-1px] text-primary">
                Reset your password
              </Heading>
              <Text className="mb-0 mt-[12px] text-center text-[16px] leading-[25px] text-secondary">
                Use the secure link below to choose a new password.
              </Text>

              <Section className="mt-[26px] rounded-[12px] border border-solid border-line bg-surfaceRaised px-[22px] py-[22px]">
                <Img
                  src={assetUrl("key-round.png")}
                  alt=""
                  width="40"
                  height="40"
                  className="mx-auto mb-[14px] block"
                />
                <Button
                  href={resetUrl}
                  className="block box-border rounded-[10px] bg-accent px-[24px] py-[15px] text-center text-[15px] font-semibold text-ink no-underline"
                >
                  Reset password
                </Button>
                <Text className="mb-0 mt-[14px] text-center text-[12px] leading-[19px] text-muted">
                  Expires in one hour · Works once
                </Text>
              </Section>

              <Section className="mt-[20px] rounded-[10px] border border-solid border-line px-[16px] py-[14px]">
                <Row>
                  <Column className="w-[38px] align-middle">
                    <Img
                      src={assetUrl("shield-check.png")}
                      alt=""
                      width="28"
                      height="28"
                      className="block"
                    />
                  </Column>
                  <Column className="align-middle">
                    <Text className="m-0 text-[13px] leading-[21px] text-secondary">
                      Didn&apos;t request this? Ignore it—your password
                      won&apos;t change.
                    </Text>
                  </Column>
                </Row>
              </Section>

              <Hr className="my-[26px] border-solid border-line" />

              <Text className="m-0 text-[12px] leading-[20px] text-muted">
                Or use this link:
              </Text>
              <Link
                href={resetUrl}
                className="mt-[6px] block break-all text-[12px] leading-[19px] text-accentSoft underline"
              >
                {resetUrl}
              </Link>
            </Section>

            <Section className="border-none border-t border-solid border-t-line px-[36px] py-[22px]">
              <Row>
                <Column className="w-[34px] align-middle">
                  <Img
                    src={assetUrl("brand-mark.png")}
                    alt=""
                    width="26"
                    height="26"
                    className="block"
                  />
                </Column>
                <Column className="align-middle">
                  <Text className="m-0 text-[11px] leading-[18px] text-muted">
                    Signal Copier · Secure MT5 controls
                  </Text>
                </Column>
              </Row>
            </Section>
          </Container>
        </Body>
      </Tailwind>
    </Html>
  );
}

PasswordResetEmail.PreviewProps = {
  assetBaseUrl: "http://localhost:3000",
  resetUrl:
    "https://dashboard.kiaparsaprintingmoneymachine.cloud/sign-in/reset-password?token=preview-token",
} satisfies PasswordResetEmailProps;

export default PasswordResetEmail;
