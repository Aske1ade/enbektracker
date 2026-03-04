import {
  Badge,
  Container,
  Heading,
  Radio,
  RadioGroup,
  Stack,
  useColorMode,
} from "@chakra-ui/react"

const Appearance = () => {
  const { colorMode, toggleColorMode } = useColorMode()

  return (
    <>
      <Container maxW="full">
        <Heading size="sm" py={4}>
          Тема интерфейса
        </Heading>
        <RadioGroup
          onChange={(nextMode) => {
            if (nextMode !== colorMode) {
              toggleColorMode()
            }
          }}
          value={colorMode}
        >
          <Stack>
            {/* TODO: Add system default option */}
            <Radio value="light" colorScheme="teal">
              Светлая тема
              <Badge ml="1" colorScheme="teal">
                По умолчанию
              </Badge>
            </Radio>
            <Radio value="dark" colorScheme="teal">
              Тёмная тема
            </Radio>
          </Stack>
        </RadioGroup>
      </Container>
    </>
  )
}
export default Appearance
