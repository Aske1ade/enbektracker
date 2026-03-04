import {
  Box,
  Button,
  ButtonGroup,
  HStack,
  Icon,
  Tooltip,
} from "@chakra-ui/react"
import { useEffect, useMemo, useRef } from "react"
import {
  FiBold,
  FiCheckSquare,
  FiItalic,
  FiList,
  FiType,
  FiUnderline,
} from "react-icons/fi"

type RichTextEditorProps = {
  value: string
  onChange: (value: string) => void
  minH?: string
  placeholder?: string
}

type EditorAction = {
  icon: typeof FiBold
  label: string
  command: string
  value?: string
}

const formattingActions: EditorAction[] = [
  { icon: FiBold, label: "Жирный", command: "bold" },
  { icon: FiItalic, label: "Курсив", command: "italic" },
  { icon: FiUnderline, label: "Подчеркнутый", command: "underline" },
  { icon: FiType, label: "Заголовок", command: "formatBlock", value: "h3" },
  {
    icon: FiList,
    label: "Маркированный список",
    command: "insertUnorderedList",
  },
  {
    icon: FiList,
    label: "Нумерованный список",
    command: "insertOrderedList",
  },
]

export default function RichTextEditor({
  value,
  onChange,
  minH = "180px",
  placeholder,
}: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const editor = editorRef.current
    if (!editor) return
    if (editor.innerHTML !== value) {
      editor.innerHTML = value || ""
    }
  }, [value])

  const editorPlaceholder = useMemo(
    () => placeholder || "Опишите задачу: абзацы, списки, чек-лист, акценты",
    [placeholder],
  )

  const runCommand = (command: string, commandValue?: string) => {
    const editor = editorRef.current
    if (!editor) return
    editor.focus()
    document.execCommand(command, false, commandValue)
    onChange(editor.innerHTML)
  }

  const insertChecklist = () => {
    const editor = editorRef.current
    if (!editor) return
    editor.focus()
    document.execCommand(
      "insertHTML",
      false,
      '<ul><li><input type="checkbox" disabled /> Пункт чек-листа</li></ul>',
    )
    onChange(editor.innerHTML)
  }

  return (
    <Box
      borderWidth="1px"
      borderColor="ui.border"
      borderRadius="8px"
      bg="white"
    >
      <HStack
        justify="space-between"
        px={3}
        py={2}
        borderBottomWidth="1px"
        borderColor="ui.border"
        bg="ui.secondary"
      >
        <ButtonGroup size="xs" isAttached variant="subtle">
          {formattingActions.map((action) => (
            <Tooltip
              key={`${action.command}-${action.label}`}
              label={action.label}
            >
              <Button onClick={() => runCommand(action.command, action.value)}>
                <Icon as={action.icon} boxSize={3.5} />
              </Button>
            </Tooltip>
          ))}
          <Tooltip label="Чек-лист">
            <Button onClick={insertChecklist}>
              <Icon as={FiCheckSquare} boxSize={3.5} />
            </Button>
          </Tooltip>
        </ButtonGroup>
      </HStack>

      <Box
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        minH={minH}
        p={3}
        fontSize="sm"
        lineHeight="1.65"
        _focusVisible={{ outline: "none" }}
        onInput={(event) =>
          onChange((event.target as HTMLDivElement).innerHTML)
        }
        sx={{
          "&:empty:before": {
            content: `"${editorPlaceholder}"`,
            color: "#91A0B5",
          },
          "& ul": {
            marginLeft: "18px",
            listStyleType: "disc",
          },
          "& ol": {
            marginLeft: "18px",
            listStyleType: "decimal",
          },
          "& h3": {
            fontWeight: 700,
            fontSize: "1rem",
            marginTop: "0.35rem",
            marginBottom: "0.35rem",
          },
          "& p": {
            marginBottom: "0.35rem",
          },
          "& li": {
            marginBottom: "0.2rem",
          },
          "& input[type='checkbox']": {
            marginRight: "0.4rem",
          },
        }}
      />
    </Box>
  )
}
