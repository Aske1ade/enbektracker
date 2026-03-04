import { Box } from "@chakra-ui/react"

type RichTextContentProps = {
  value: string
  fontSize?: string
  color?: string
  noOfLines?: number
}

function sanitizeHtml(rawHtml: string): string {
  if (!rawHtml) return ""
  if (typeof window === "undefined") return rawHtml

  const parser = new DOMParser()
  const doc = parser.parseFromString(rawHtml, "text/html")

  for (const el of doc.querySelectorAll(
    "script,style,iframe,object,embed,meta,link",
  )) {
    el.remove()
  }

  for (const el of doc.querySelectorAll("*")) {
    for (const attr of [...el.attributes]) {
      const attrName = attr.name.toLowerCase()
      const attrValue = attr.value.trim().toLowerCase()
      if (attrName.startsWith("on")) {
        el.removeAttribute(attr.name)
        continue
      }
      if (
        (attrName === "href" || attrName === "src") &&
        attrValue.startsWith("javascript:")
      ) {
        el.removeAttribute(attr.name)
      }
    }

    if (el.tagName === "INPUT") {
      const input = el as HTMLInputElement
      if (input.type !== "checkbox") {
        el.remove()
      } else {
        input.disabled = true
      }
    }
  }

  return doc.body.innerHTML
}

export function htmlToText(rawHtml: string): string {
  if (!rawHtml) return ""
  if (typeof window === "undefined") {
    return rawHtml
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
  }
  const parser = new DOMParser()
  const doc = parser.parseFromString(rawHtml, "text/html")
  return (doc.body.textContent || "").replace(/\s+/g, " ").trim()
}

export default function RichTextContent({
  value,
  fontSize = "sm",
  color = "ui.text",
  noOfLines,
}: RichTextContentProps) {
  const safeHtml = sanitizeHtml(value)

  return (
    <Box
      fontSize={fontSize}
      color={color}
      noOfLines={noOfLines}
      sx={{
        "& ul": { marginLeft: "18px", listStyleType: "disc" },
        "& ol": { marginLeft: "18px", listStyleType: "decimal" },
        "& li": { marginBottom: "0.25rem" },
        "& input[type='checkbox']": { marginRight: "0.45rem" },
        "& p": { marginBottom: "0.35rem" },
        "& h3": { fontSize: "1rem", fontWeight: 700, marginBottom: "0.3rem" },
      }}
      // biome-ignore lint/security/noDangerouslySetInnerHtml: content is sanitized in sanitizeHtml().
      dangerouslySetInnerHTML={{ __html: safeHtml }}
    />
  )
}
