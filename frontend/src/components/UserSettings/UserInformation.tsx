import {
  Avatar,
  Box,
  Button,
  Container,
  Flex,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Heading,
  Input,
  InputGroup,
  InputRightAddon,
  Text,
  useColorModeValue,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"

import {
  type ApiError,
  type UserPublic,
  type UserUpdateMe,
  UsersService,
} from "../../client"
import useAuth from "../../hooks/useAuth"
import useCustomToast from "../../hooks/useCustomToast"
import {
  clearUserAvatar,
  readUserAvatar,
  writeUserAvatar,
} from "../../hooks/useUserAvatar"
import { emailPattern } from "../../utils"

const UserInformation = () => {
  const queryClient = useQueryClient()
  const color = useColorModeValue("inherit", "ui.light")
  const cardBg = useColorModeValue("white", "#162235")
  const showToast = useCustomToast()
  const [editMode, setEditMode] = useState(false)
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null)
  const { user: currentUser } = useAuth()
  const {
    register,
    handleSubmit,
    reset,
    getValues,
    formState: { isSubmitting, errors, isDirty },
  } = useForm<UserPublic>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      full_name: currentUser?.full_name,
      email: currentUser?.email,
    },
  })

  const toggleEditMode = () => {
    setEditMode(!editMode)
  }

  useEffect(() => {
    setAvatarSrc(readUserAvatar(currentUser?.id))
  }, [currentUser?.id])

  const mutation = useMutation({
    mutationFn: (data: UserUpdateMe) =>
      UsersService.updateUserMe({ requestBody: data }),
    onSuccess: () => {
      showToast.success("Успешно", "Профиль обновлён")
    },
    onError: (err: ApiError) => {
      const errDetail = (err.body as any)?.detail
      showToast.error("Не удалось обновить профиль", `${errDetail}`)
    },
    onSettled: () => {
      // TODO: can we do just one call now?
      queryClient.invalidateQueries({ queryKey: ["users"] })
      queryClient.invalidateQueries({ queryKey: ["currentUser"] })
    },
  })

  const onSubmit: SubmitHandler<UserUpdateMe> = async (data) => {
    mutation.mutate(data)
  }

  const onCancel = () => {
    reset()
    toggleEditMode()
  }

  const onAvatarPicked = async (file: File | undefined) => {
    if (!file || !currentUser?.id) return
    if (!file.type.startsWith("image/")) {
      showToast.error("Некорректный файл", "Выберите изображение")
      return
    }
    if (file.size > 1024 * 1024) {
      showToast.error("Слишком большой файл", "Максимум 1 MB")
      return
    }
    const dataUrl = await fileToDataUrl(file)
    writeUserAvatar(currentUser.id, dataUrl)
    setAvatarSrc(dataUrl)
    showToast.success("Успешно", "Аватар обновлён")
  }

  return (
    <>
      <Container maxW="full">
        <Heading size="sm" py={4}>
          Основной профиль
        </Heading>
        <Flex
          mb={6}
          p={4}
          borderWidth="1px"
          borderColor="ui.border"
          borderRadius="md"
          bg={cardBg}
          align={{ base: "start", md: "center" }}
          direction={{ base: "column", md: "row" }}
          gap={4}
        >
          <Avatar
            size="xl"
            name={currentUser?.full_name || currentUser?.email}
            src={avatarSrc || undefined}
          />
          <Box>
            <Text fontWeight="600" mb={2}>
              Аватар профиля
            </Text>
            <InputGroup size="sm" maxW="360px">
              <Input
                type="file"
                accept="image/*"
                onChange={(event) =>
                  onAvatarPicked(event.target.files?.[0] || undefined)
                }
                p={1}
              />
              <InputRightAddon p={0} border="none" bg="transparent">
                <Button
                  size="sm"
                  variant="subtle"
                  onClick={() => {
                    clearUserAvatar(currentUser?.id)
                    setAvatarSrc(null)
                  }}
                >
                  Удалить
                </Button>
              </InputRightAddon>
            </InputGroup>
            <Text mt={2} fontSize="xs" color="ui.muted">
              Локальный профильный аватар (до 1 MB, png/jpg/webp)
            </Text>
          </Box>
        </Flex>
        <Box
          w={{ sm: "full", md: "50%" }}
          as="form"
          onSubmit={handleSubmit(onSubmit)}
        >
          <FormControl>
            <FormLabel color={color} htmlFor="name">
              ФИО
            </FormLabel>
            {editMode ? (
              <Input
                id="name"
                {...register("full_name", { maxLength: 30 })}
                type="text"
                size="md"
              />
            ) : (
              <Text
                size="md"
                py={2}
                color={!currentUser?.full_name ? "ui.dim" : "inherit"}
              >
                {currentUser?.full_name || "Не указано"}
              </Text>
            )}
          </FormControl>
          <FormControl mt={4} isInvalid={!!errors.email}>
            <FormLabel color={color} htmlFor="email">
              Email
            </FormLabel>
            {editMode ? (
              <Input
                id="email"
                {...register("email", {
                  required: "Email обязателен",
                  pattern: emailPattern,
                })}
                type="email"
                size="md"
              />
            ) : (
              <Text size="md" py={2}>
                {currentUser?.email}
              </Text>
            )}
            {errors.email && (
              <FormErrorMessage>{errors.email.message}</FormErrorMessage>
            )}
          </FormControl>
          <Flex mt={4} gap={3}>
            <Button
              variant="primary"
              onClick={toggleEditMode}
              type={editMode ? "button" : "submit"}
              isLoading={editMode ? isSubmitting : false}
              isDisabled={editMode ? !isDirty || !getValues("email") : false}
            >
              {editMode ? "Сохранить" : "Редактировать"}
            </Button>
            {editMode && (
              <Button onClick={onCancel} isDisabled={isSubmitting}>
                Отмена
              </Button>
            )}
          </Flex>
        </Box>
      </Container>
    </>
  )
}

export default UserInformation

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error("Не удалось прочитать файл"))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(file)
  })
}
