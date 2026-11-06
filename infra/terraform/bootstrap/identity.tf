resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
locals {
  oidc_arn     = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : "arn:aws:iam::${local.account}:oidc-provider/token.actions.githubusercontent.com"
  environments = { infrastructure = ["infrastructure", "destruction"], delivery = ["production"] }
}
resource "aws_iam_role" "ci" {
  for_each             = local.environments
  name                 = "${var.project}-${each.key}"
  max_session_duration = 3600
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRoleWithWebIdentity", Principal = { Federated = local.oidc_arn },
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub" = [for environment in each.value : "${var.github_oidc_subject_prefix}:environment:${environment}"]
    } }
  }] })
}
resource "aws_iam_role" "runtime" {
  name               = "${var.project}-runtime"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }] })
}
resource "aws_iam_instance_profile" "runtime" {
  name = "${var.project}-runtime"
  role = aws_iam_role.runtime.name
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.runtime.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "runtime" {
  role = aws_iam_role.runtime.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Sid      = "QwenOnly", Effect = "Allow", Action = ["bedrock-mantle:CreateInference"],
      Resource = "arn:aws:bedrock-mantle:${var.aws_region}:${local.account}:project/*",
    Condition = { StringEquals = { "bedrock-mantle:Model" = "qwen.qwen3-32b" } } },
    { Sid = "ShortLivedToken", Effect = "Allow", Action = ["bedrock-mantle:CallWithBearerToken"], Resource = "*", Condition = { StringEquals = { "aws:RequestedRegion" = var.aws_region } } },
    { Sid = "PullImages", Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability", "ecr:DescribeImages"], Resource = [for repo in aws_ecr_repository.images : repo.arn] },
    { Sid = "RegistryLogin", Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Sid = "ReleaseManifest", Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.releases.arn}/releases/*.json" },
    { Sid = "AdminPassword", Effect = "Allow", Action = ["ssm:GetParameter"], Resource = local.parameter_arn }
  ] })
}
resource "aws_ssm_document" "deploy" {
  name          = "${var.project}-deploy-release"
  document_type = "Command"
  content = jsonencode({ schemaVersion = "2.2", description = "Implantar apenas manifesto de release validado, sem shell fornecido pelo CI",
    parameters = { CommitId = { type = "String", allowedPattern = "^[a-f0-9]{40}$" } },
    mainSteps  = [{ action = "aws:runShellScript", name = "deploy", inputs = { timeoutSeconds = "1800", runCommand = ["set -eu", "cloud-init status --wait", "install -d -m 0700 /run/ml-game", "printf '%s\\n' '{{ CommitId }}' > /run/ml-game/requested-release", "systemctl reload-or-restart ml-game.service"] } }]
  })
}
resource "aws_iam_role_policy" "delivery" {
  role = aws_iam_role.ci["delivery"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.state.arn}/${local.bootstrap_key}" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:DescribeImages", "ecr:DescribeImageScanFindings"], Resource = [for repo in aws_ecr_repository.images : repo.arn] },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.releases.arn}/releases/*.json" },
    { Effect = "Allow", Action = ["ssm:SendCommand"], Resource = aws_ssm_document.deploy.arn },
    { Effect = "Allow", Action = ["ssm:SendCommand"], Resource = "arn:aws:ec2:${var.aws_region}:${local.account}:instance/*", Condition = { StringEquals = { "ssm:resourceTag/Project" = var.project } } },
    { Effect = "Allow", Action = ["ssm:GetCommandInvocation", "ssm:DescribeInstanceInformation", "ec2:DescribeInstances"], Resource = "*" }
  ] })
}
resource "aws_ssm_document" "admin_tunnel" {
  name          = "${var.project}-admin-tunnel"
  document_type = "Session"
  content = jsonencode({ schemaVersion = "1.0", description = "Túnel somente para o admin local 7078", sessionType = "Port",
    parameters = { localPortNumber = { type = "String", default = "7078", allowedPattern = "^[0-9]{1,5}$" } },
    properties = { portNumber = "7078", type = "LocalPortForwarding", localPortNumber = "{{ localPortNumber }}" }
  })
}
resource "aws_iam_policy" "admin_tunnel" {
  name        = "${var.project}-admin-tunnel"
  description = "Anexar somente aos operadores, não aos jogadores ou papel do CI"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ssm:StartSession"], Resource = "arn:aws:ec2:${var.aws_region}:${local.account}:instance/*", Condition = { StringEquals = { "ssm:resourceTag/Project" = var.project } } },
    { Effect = "Allow", Action = ["ssm:StartSession"], Resource = aws_ssm_document.admin_tunnel.arn },
    { Effect = "Allow", Action = ["ssm:TerminateSession"], Resource = "arn:aws:ssm:${var.aws_region}:${local.account}:session/*", Condition = { StringEquals = { "ssm:resourceTag/aws:ssmmessages:session-id" = "$${aws:userid}" } } },
    { Effect = "Allow", Action = ["ec2:DescribeInstances", "ssm:DescribeInstanceInformation"], Resource = "*" }
  ] })
}
