locals {
  ec2         = "arn:aws:ec2:${var.aws_region}:${local.account}"
  elb         = "arn:aws:elasticloadbalancing:${var.aws_region}:${local.account}"
  subnet_arns = [for subnet in aws_subnet.public : subnet.arn]
}
resource "aws_iam_role_policy" "infrastructure" {
  role = aws_iam_role.ci["infrastructure"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Sid = "ReadCloudMetadata", Effect = "Allow", Action = ["ec2:Describe*", "elasticloadbalancing:Describe*", "acm:ListCertificates"], Resource = "*" },
    { Sid = "PublicAMIParameter", Effect = "Allow", Action = ["ssm:GetParameter"], Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" },
    { Sid = "NoSecretsInInfra", Effect = "Deny", Action = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"], Resource = "arn:aws:ssm:${var.aws_region}:${local.account}:parameter/memorias-licantropicas/*" },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.state.arn },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.state.arn}/${local.bootstrap_key}" },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = ["${aws_s3_bucket.state.arn}/${local.state_key}", "${aws_s3_bucket.state.arn}/${local.state_key}.tflock"] },
    { Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "${aws_s3_bucket.state.arn}/${local.state_key}.tflock" },
    { Sid = "UseFixedProfile", Effect = "Allow", Action = ["iam:PassRole"], Resource = aws_iam_role.runtime.arn, Condition = { StringEquals = { "iam:PassedToService" = "ec2.amazonaws.com" } } },
    { Effect = "Allow", Action = ["iam:GetInstanceProfile"], Resource = aws_iam_instance_profile.runtime.arn },
    { Sid = "RunOnlyRequestedSize", Effect = "Allow", Action = ["ec2:RunInstances"], Resource = "${local.ec2}:instance/*", Condition = { StringEquals = { "aws:RequestTag/Project" = var.project, "ec2:InstanceType" = "m7i-flex.large", "ec2:MetadataHttpTokens" = "required" } } },
    { Effect = "Allow", Action = ["ec2:RunInstances"], Resource = ["arn:aws:ec2:${var.aws_region}::image/*", "${local.ec2}:network-interface/*"] },
    { Effect = "Allow", Action = ["ec2:RunInstances"], Resource = local.subnet_arns },
    { Effect = "Allow", Action = ["ec2:RunInstances"], Resource = "${local.ec2}:security-group/*", Condition = { StringEquals = { "ec2:ResourceTag/Project" = var.project } } },
    { Effect = "Allow", Action = ["ec2:RunInstances"], Resource = "${local.ec2}:volume/*", Condition = { StringEquals = { "aws:RequestTag/Project" = var.project }, Bool = { "ec2:Encrypted" = "true" } } },
    { Effect = "Allow", Action = ["ec2:CreateSecurityGroup"], Resource = ["${local.ec2}:security-group/*", aws_vpc.game.arn] },
    { Effect = "Allow", Action = ["ec2:CreateTags"], Resource = ["${local.ec2}:instance/*", "${local.ec2}:volume/*", "${local.ec2}:network-interface/*", "${local.ec2}:security-group/*", "${local.ec2}:security-group-rule/*"], Condition = { StringEquals = { "aws:RequestTag/Project" = var.project, "ec2:CreateAction" = ["RunInstances", "CreateSecurityGroup", "AuthorizeSecurityGroupIngress", "AuthorizeSecurityGroupEgress"] } } },
    { Effect = "Allow", Action = ["ec2:TerminateInstances", "ec2:StopInstances", "ec2:StartInstances", "ec2:ModifyInstanceAttribute", "ec2:ModifySecurityGroupRules", "ec2:CreateTags", "ec2:DeleteSecurityGroup", "ec2:AuthorizeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress", "ec2:RevokeSecurityGroupIngress", "ec2:RevokeSecurityGroupEgress", "ec2:DeleteTags"], Resource = ["${local.ec2}:instance/*", "${local.ec2}:security-group/*", "${local.ec2}:volume/*", "${local.ec2}:security-group-rule/*"], Condition = { StringEquals = { "ec2:ResourceTag/Project" = var.project } } },
    { Sid = "KeepIMDSv2Required", Effect = "Allow", Action = ["ec2:ModifyInstanceMetadataOptions"], Resource = "${local.ec2}:instance/*", Condition = { StringEquals = { "ec2:ResourceTag/Project" = var.project, "ec2:MetadataHttpTokens" = "required" } } },
    { Sid = "NoOtherInstanceSize", Effect = "Deny", Action = ["ec2:ModifyInstanceAttribute"], Resource = "${local.ec2}:instance/*", Condition = { StringNotEquals = { "ec2:Attribute/InstanceType" = "m7i-flex.large" }, Null = { "ec2:Attribute/InstanceType" = "false" } } },
    { Effect = "Allow", Action = ["ec2:AttachVolume", "ec2:DetachVolume"], Resource = [aws_ebs_volume.data.arn, "${local.ec2}:instance/*"], Condition = { StringEquals = { "ec2:ResourceTag/Project" = var.project } } },
    { Sid = "ApplicationLoadBalancer", Effect = "Allow", Action = ["elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:DeleteLoadBalancer", "elasticloadbalancing:ModifyLoadBalancerAttributes", "elasticloadbalancing:SetSecurityGroups", "elasticloadbalancing:SetSubnets", "elasticloadbalancing:CreateTargetGroup", "elasticloadbalancing:DeleteTargetGroup", "elasticloadbalancing:ModifyTargetGroup", "elasticloadbalancing:ModifyTargetGroupAttributes", "elasticloadbalancing:RegisterTargets", "elasticloadbalancing:DeregisterTargets", "elasticloadbalancing:CreateListener", "elasticloadbalancing:DeleteListener", "elasticloadbalancing:ModifyListener", "elasticloadbalancing:AddTags", "elasticloadbalancing:RemoveTags"], Resource = ["${local.elb}:loadbalancer/app/mlgame-*/*", "${local.elb}:targetgroup/mlgame-*/*", "${local.elb}:listener/app/mlgame-*/*/*"] },
    { Effect = "Allow", Action = ["iam:CreateServiceLinkedRole"], Resource = "arn:aws:iam::${local.account}:role/aws-service-role/elasticloadbalancing.amazonaws.com/AWSServiceRoleForElasticLoadBalancing", Condition = { StringEquals = { "iam:AWSServiceName" = "elasticloadbalancing.amazonaws.com" } } },
    { Effect = "Allow", Action = ["acm:DescribeCertificate"], Resource = aws_acm_certificate.game.arn },
    { Effect = "Allow", Action = ["route53:GetHostedZone", "route53:ListResourceRecordSets"], Resource = aws_route53_zone.game.arn },
    { Effect = "Allow", Action = ["route53:GetChange"], Resource = "arn:aws:route53:::change/*" },
    { Effect = "Allow", Action = ["route53:ChangeResourceRecordSets"], Resource = aws_route53_zone.game.arn, Condition = { "ForAllValues:StringLike" = { "route53:ChangeResourceRecordSetsNormalizedRecordNames" = [var.domain_name] }, "ForAllValues:StringEquals" = { "route53:ChangeResourceRecordSetsRecordTypes" = ["A"] } } }
  ] })
}
